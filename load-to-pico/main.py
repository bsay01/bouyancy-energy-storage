"""
* ECE 399 Group 14

# DESC:

    Wiring:

        GP18-21 to debugging LEDs
        GP16 to kill switch (active low)
        GP17 to mode switch (active low)

        STEPPER MOTOR WIRING - L298N Stepper Motor Driver
            this project used a 24V Bipolar stepper rated for 1.4 A
            [  GP1 , GP3 , GP4 , GP2 , GP5 , GP6 ]
            [  ENA , IN1 , IN2 , ENB , IN3 , IN4 ]

    written for a Pico W running on a Micropython OS
    Thonny can automatically connect to and interface with Micropython systems - see https://thonny.org/

    starts in generator mode

"""

import utime, machine, BlynkLib, network, BlynkTimer, _thread, sys

#########################################################################################
####################################### DEFINES #########################################
#########################################################################################

interrupt_state = machine.disable_irq()
machine.enable_irq(interrupt_state)

#### Blynk globals ####

BLYNK_TEMPLATE_ID = "TMPL2UsApXL1s"
BLYNK_TEMPLATE_NAME = "Quickstart Template"
BLYNK_AUTH_TOKEN = "NKV7_l21Ch2v0buSwwvqLU0zDpwA2dEP"

GENERATE_SWITCH_VPIN = 0
POWER_VPIN = 1
KILLSWITCH_VPIN = 2
MAX_POWER_VPIN = 3
TOTAL_ENERGY_GENERATED_VPIN = 4

BLYNK_UPDATE_INTERVAL = 1 # seconds

#### ADC globals ####
ADC_UPDATE_INTERVAL = 20 # milliseconds
N_adc_samples = 1        # number of ADC samples since last blynk update
adc_sums = [0.0, 0.0]    # sums of ADC samples for averaging
adc_avgs = [0.0, 0.0]    # ADC averages
adc_max = 0
energy_generated = 0

#### WiFi Stuff ####

MAX_NETWORK_CONNECTION_ERRORS_ALLOWED = 5
MAX_NETWORK_CONNECTION_ATTEMPTS_ALLOWED = 3

WIFI_NAME =  'Lee'

known_wifi_passwords = {
    'bens-surface': 'wiggles101',       # ben's surface
    'SHAW-E8C2': 'breezy2116fever',     # home network
    'the Groove Machine': 'wiggles101', # ben's phone
    'Liams Iphone XR': 'colemansgimp',  # liam's phone
    'Lee': 'leeroijenkins'              # sam's phone
}

#### Stepper Stuff ####

MIN_STEP_DELAY = 6
MAX_STEP_DELAY = 20

STEPS_TO_BOTTOM = 4800
SPIN_CW = False

stepper_signals = {
    1 : [1, 1, 0, 1, 1, 0],
    2 : [1, 0, 1, 1, 1, 0],
    3 : [1, 0, 1, 1, 0, 1],
    4 : [1, 1, 0, 1, 0, 1]
}

#########################################################################################
################################### PIN DEFINITIONS #####################################
#########################################################################################

killswitch_button = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_UP)
generate_button = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_UP)

LED_pins = [
    machine.Pin(18, machine.Pin.OUT, machine.Pin.PULL_DOWN), # LED1
    machine.Pin(19, machine.Pin.OUT, machine.Pin.PULL_DOWN), # LED2
    machine.Pin(20, machine.Pin.OUT, machine.Pin.PULL_DOWN), # LED3
    machine.Pin(21, machine.Pin.OUT, machine.Pin.PULL_DOWN)  # LED4
]

stepper_pins = [
    machine.Pin(0, machine.Pin.OUT), # ENA
    machine.Pin(2, machine.Pin.OUT), # IN1
    machine.Pin(3, machine.Pin.OUT), # IN2
    machine.Pin(1, machine.Pin.OUT), # ENB
    machine.Pin(4, machine.Pin.OUT), # IN3
    machine.Pin(5, machine.Pin.OUT)  # IN4
]

RELAY1 = machine.Pin(14, machine.Pin.OUT, machine.Pin.PULL_DOWN)
RELAY2 = machine.Pin(15, machine.Pin.OUT, machine.Pin.PULL_DOWN)

# set up ADC0 to read voltage from amplifiers and ADC1 to read current from amplifiers
#adc = [machine.ADC(machine.Pin(26)), machine.ADC(machine.Pin(27))]
adc0 = machine.ADC(machine.Pin(26))
adc1 = machine.ADC(machine.Pin(27))

#########################################################################################
################################### GLOBAL VARIABLES ####################################
#########################################################################################

stepper_state = 1

generate = True
was_generating = True

kill = False

#########################################################################################
###################################### FUNCTIONS ########################################
#########################################################################################

### LEDs ###

def show_on_LEDs(list):
    global LED_pins
    for pin, value in zip(LED_pins, list):
        pin.value(value)

def flash_LEDs(times = 1, delay = 100):
    show_on_LEDs([0, 0, 0, 0])
    for x in range(times):
        show_on_LEDs([1, 1, 1, 1])
        utime.sleep_ms(delay)
        show_on_LEDs([0, 0, 0, 0])
        utime.sleep_ms(delay)

def sweep_LEDs(times = 1, up = True, delay = 50):
    show_on_LEDs([0, 0, 0, 0])
    increment = 1 if up is True else -1
    rng = [1, 5] if up is True else [4, 0]
    for x in range(times):
        for x in range(rng[0], rng[1], increment):
            L = [0, 0, 0, 0]
            L[x-1] = 1
            show_on_LEDs(L)
            utime.sleep_ms(delay)
    show_on_LEDs([0, 0, 0, 0])

### RELAYS ###

def disable_generator():
    RELAY1.value(0)
    RELAY2.value(1)
    print("generator disabled")

def enable_generator():
    RELAY1.value(1)
    RELAY2.value(0)
    print("generator enabled")

### STEPPER COMMUNICATION ###

def send_stepper_signal(list):
    global stepper_pins
    for pin, value in zip(stepper_pins, list):
        pin.value(value)
    show_on_LEDs([list[1], list[2], list[4], list[5]])

def disable_stepper():
    send_stepper_signal([0, 0, 0, 0, 0, 0])
    print("stepper disabled")

def brake_stepper():
    send_stepper_signal([1, 0, 0, 1, 0, 0])
    print("stepper braked")

### SHORTCUTS ###

def initialize_hardware(step_delay = 200):
    print("beginning hardware setup process...")
    disable_generator()
    show_on_LEDs([1, 0, 0, 0])
    utime.sleep_ms(step_delay)
    disable_stepper()
    show_on_LEDs([1, 1, 0, 0])
    utime.sleep_ms(step_delay)
    enable_generator()
    show_on_LEDs([1, 1, 1, 0])
    utime.sleep_ms(step_delay)
    print("\nhardware setup complete!\n")
    show_on_LEDs([1, 1, 1, 1])
    flash_LEDs(2)

# creates noticeable buffer time between killswitch triggers
def killswitch_pause():
    print("\nkill switch detected, disabling button (and system, for safety)...")
    show_on_LEDs([1, 1, 1, 1])
    disable_stepper()
    show_on_LEDs([1, 1, 1, 1])
    utime.sleep_ms(50)
    disable_generator()
    utime.sleep_ms(2000)
    print("kill switch re-enabled")
    show_on_LEDs([0, 0, 0, 0])

def connect_to_WiFi_network(ssid = 'bens-surface'):

    sta_if = network.WLAN(network.STA_IF)

    print('connecting to WiFi network "{}"...'.format(WIFI_NAME))
    sta_if.active(True)

    errors_counted = 0
    attempts = 1

    try:
        sta_if.connect(ssid, known_wifi_passwords[ssid])
    except:
        print("WIFI CONNECT EXCEPTION - on attempt {}".format(attempts))

    while not sta_if.isconnected():

        stat = sta_if.status()

        if stat is network.STAT_IDLE:
            print("idle...")
        elif stat is network.STAT_GOT_IP:
            print("IP recieved...")
        elif stat is network.STAT_CONNECTING:
            print("connecting...")
        elif stat is network.STAT_NO_AP_FOUND:
            print("ERROR: AP not found...")
        elif stat is network.STAT_CONNECT_FAIL:
            print("ERROR: misc. connection failure...")
        elif stat is network.STAT_WRONG_PASSWORD:
            print("ERROR: incorrect password error recieved...")
        else:
            print("ERROR: unknown network status case...")

        if stat is not (network.STAT_IDLE or network.STAT_GOT_IP or network.STAT_CONNECTING):
            if errors_counted >= MAX_NETWORK_CONNECTION_ERRORS_ALLOWED:
                print("too many ({}) errors in a row. restarting connection...".format(errors_counted))
                attempts = attempts + 1
                errors_counted = 0
                try:
                    print("begin connection attempt {}...".format(attempts))
                    sta_if.connect(ssid, known_wifi_passwords[ssid])
                except:
                    print("WIFI CONNECT EXCEPTION - on attempt {}".format(attempts))
            else:
                errors_counted = errors_counted + 1

        if attempts >= MAX_NETWORK_CONNECTION_ATTEMPTS_ALLOWED:
            print("network connection attempt limit reached ({}). restarting system.".format(attempts))
            sys.exit()

        sweep_LEDs(7)

    print("network connected!")
    print('network configuration: ', sta_if.ifconfig())
    print()
    sweep_LEDs(1, False)

    return sta_if

def move_stepper(steps_to_move = 200, CW = True, delay = MIN_STEP_DELAY):
    global generate
    global stepper_state
    global stepper_signals
    for step in range(steps_to_move):
        if generate is True:
            return False
        if CW is True:
            stepper_state = (stepper_state + 1) if stepper_state < 4 else 1
        elif CW is False:
            stepper_state = (stepper_state - 1) if stepper_state > 1 else 4
        else:
            raise Exception("CW case error: {}".format(CW))
        try:
            send_stepper_signal(stepper_signals[stepper_state])
        except:
            raise Exception("stepper_state case error: {}".format(stepper_state))
        utime.sleep_ms(delay)

    return True

def calibrate_stepper():
    disable_generator()
    print("calibrating motor...")
    move_stepper(67, True, 1)
    print("calibration complete! resetting...\n")
    utime.sleep_ms(500)
    move_stepper(18, False, MIN_STEP_DELAY)
    utime.sleep_ms(1000)

#########################################################################################
##################################### INTERRUPTS ########################################
#########################################################################################

# deals with killswitch button trigger
def killswitch_handler(void):
    global kill
    killswitch_pause()
    kill = False if kill is True else True
    handle_kill_state_change()

# deals with generate button trigger
def generate_handler(void):
    global generate
    print("\ngenerate button pressed, switching modes...")
    utime.sleep_ms(100)
    generate = False if generate is True else True
    handle_generate_state_change()

#########################################################################################
#################################### SET UP SYSTEM ######################################
#########################################################################################

# define interrupts
killswitch_button.irq(trigger = machine.Pin.IRQ_FALLING, handler = killswitch_handler)
generate_button.irq(trigger = machine.Pin.IRQ_FALLING, handler = generate_handler)

# set hardware to initial state
initialize_hardware()

# connect to wifi
sta_if = connect_to_WiFi_network(WIFI_NAME)

#########################################################################################
#################################### SET UP BLYNK #######################################
#########################################################################################

print("Initializing Blynk instance...")
show_on_LEDs([1, 1, 1, 1])
blynk_instance = BlynkLib.Blynk(BLYNK_AUTH_TOKEN, insecure = True)
#blynk_instance = BlynkLib.Blynk(BLYNK_AUTH_TOKEN)
show_on_LEDs([0, 0, 0, 0])

# recursive blynk function... TODO: implement properly
"""
#ret = 0
def blynk_connect_recursive(bli_inst = 0):
    global BLYNK_AUTH_TOKEN
    #global ret
    ret = bli_inst
    #if ret is not 0:
    #    return ret
    try:
        bli_inst = BlynkLib.Blynk(BLYNK_AUTH_TOKEN, insecure = True)
    except:
        print("blynk connect error, trying again")
        ret = blynk_connect_recursive(bli_inst)
    return ret

blynk_instance = blynk_connect_recursive()
"""

# HANDLERS FOR DATA COMING FROM THE BLYNK DASHBOARD

# updates the dashboard upon connection
@blynk_instance.on("connected")
def blynk_connected():
    global generate
    global kill
    print("Blynk server connected!")
    print("Updating Blynk server...")
    update_dashboard_power()
    blynk_instance.virtual_write(GENERATE_SWITCH_VPIN, 1 if generate is True else 0)
    blynk_instance.virtual_write(KILLSWITCH_VPIN, 1 if kill is True else 0)
    print("Blynk server update complete. Starting system...\n")

# recieves killswitch commands from the dashboard
@blynk_instance.on("V{}".format(KILLSWITCH_VPIN))
def v2_write_handler(value):
    global kill
    killswitch_pause()
    if value[0] is "1":
        kill = True
    elif value[0] is "0":
        kill = False
    else:
        raise Exception("kill case error on Blynk switch: {}".format(value[0]))
    handle_kill_state_change()

# recieves generate switch commands from the dashboard
@blynk_instance.on("V{}".format(GENERATE_SWITCH_VPIN))
def v0_write_handler(value):
    global generate
    print("\ngenerate button pressed, switching modes...")
    if value[0] is "0":
        generate = False
    elif value[0] is "1":
        generate = True
    else:
        raise Exception("generate case error on Blynk switch: {}".format(value[0]))
    handle_generate_state_change()

# HANDLERS FOR DATA GOING TO THE BLYNK DASHBOARD

# updates labels on the dashboard
def update_dashboard_power():

    global generate
    global N_adc_samples
    global adc_sums
    global adc_avgs
    global adc_max
    global energy_generated

    if N_adc_samples is 0:

        print("ADC averaging incomplete - dashboard not updated\n")

    else:

        adc_avgs = [sum/N_adc_samples for sum in adc_sums]
        adc_sums = [0.0 for sum in adc_sums]

        w = 0

        if generate is True:

            current = (3.3/(0.55*5))*adc_avgs[0]
            voltage = 4*3.3*adc_avgs[1]

            print("GENERATOR:")

            w = (3.3/(0.55*5))*4*3.3*adc_max
            print("max power generated: {p:.6f} W".format(p=w))

            energy_generated = energy_generated + voltage*current*BLYNK_UPDATE_INTERVAL
            print("total energy generated: {e:.6f} J".format(e=energy_generated))
            blynk_instance.virtual_write(TOTAL_ENERGY_GENERATED_VPIN, energy_generated)

        else:

            current = (3.3/(0.5*5))*adc_avgs[0]
            voltage = 4*3.3*adc_avgs[1]

            print("MOTOR:")

            w = (3.3/(0.5*5))*4*3.3*adc_max
            print("max power used: {p:.6f} W".format(p=w))

        print("ADC0: {d:.6f}, voltage: {v:2.4f} V  ".format(d=adc_avgs[1], v=voltage))
        print("ADC1: {d:.6f}, current: {c:2.4f} mA".format(d=adc_avgs[0], c=current*1000))
        print("{n} samples averaged\n" .format(n=N_adc_samples))

        N_adc_samples = 0
        blynk_instance.virtual_write(MAX_POWER_VPIN, w)
        blynk_instance.virtual_write(POWER_VPIN, voltage*current)

# sets up the system after a kill command is recieved / created
def handle_kill_state_change():

    global kill
    global generate
    global was_generating

    blynk_instance.virtual_write(KILLSWITCH_VPIN, 1 if kill is True else 0)

    if kill is True:

        print("\nSYSTEM KILL COMPLETE\n")

    elif kill is False:

        print("\nRESTARTING SYSTEM\n")
        sys.exit()
        initialize_hardware()

        generate = True
        was_generating = True

# sets up the system after a generate / drive command is recieved / created
def handle_generate_state_change():

    global generate
    global was_generating
    global N_adc_samples
    global adc_sums
    global adc_max
    global energy_generated

    blynk_instance.virtual_write(GENERATE_SWITCH_VPIN, 1 if generate is True else 0)

    if generate is False:

        print("\nswitching to motor mode...\n")

        was_generating = True
        send_stepper_signal([1, 0, 0, 1, 0, 0]) # send active signal
        disable_generator() # let active signal pass through

        utime.sleep_ms(10) # wait for relays to close and then some

    elif generate is True:

        print("\nswitching to generate mode...\n")

        enable_generator() # do this first so that no current flows back into motor controller
        utime.sleep_ms(10) # wait for relays to open
        disable_stepper()  # send stepper disable signal

        print()

    adc_sums[0] = 0
    adc_sums[1] = 0
    N_adc_samples = 0
    adc_max = 0
    energy_generated = 0

# samples and sums ADC values for later averaging
def sample_adcs(void):

    global adc_sums
    global N_adc_samples
    global adc_max

    try:

        a0 = adc0.read_u16()/65535
        a1 = adc1.read_u16()/65535

        adc_sums[0] = adc_sums[0] + a0
        adc_sums[1] = adc_sums[1] + a1

        p = a0 * a1

    except:

        raise Exception("ADC error")

    if p > adc_max:
        adc_max = p

    N_adc_samples = N_adc_samples + 1

#########################################################################################
############################## DEFINE AND START THREAD 2 ################################
#########################################################################################

def second_thread(bi, j):

    # SET UP BLYNK TIMER FOR PERIODIC EXECUTIONS
    blynk_update_timer = BlynkTimer.BlynkTimer()
    blynk_update_timer.set_interval(BLYNK_UPDATE_INTERVAL, update_dashboard_power)

    # SET UP HARDWARE TIMER TO SAMPLE ADCS PERIODICALLY
    ADC_timer = machine.Timer(period = ADC_UPDATE_INTERVAL, mode = machine.Timer.PERIODIC, callback = sample_adcs)

    while True:
        bi.run()
        blynk_update_timer.run()

_thread.start_new_thread(second_thread, (blynk_instance, 1))

#########################################################################################
###################################### MAIN LOOP ########################################
#########################################################################################

while True:

    # make sure Pico is connected to the internet
    if not sta_if.isconnected():
        sta_if = connect_to_WiFi_network(WIFI_NAME)

    if kill is True:

        flash_LEDs(1, 500)

    elif kill is False:

        # if we are in motor mode and we were generating before
        if generate is False and was_generating is True:

            calibrate_stepper()

            # store a bunch of power and wait for the generate signal
            move_stepper(STEPS_TO_BOTTOM, SPIN_CW, MIN_STEP_DELAY)

            was_generating = False
