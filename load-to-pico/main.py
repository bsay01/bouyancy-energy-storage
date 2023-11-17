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

import utime, machine, BlynkLib, network, BlynkTimer

#########################################################################################
################################### GLOBAL VARIABLES ####################################
#########################################################################################

BLYNK_TEMPLATE_ID = "TMPL2UsApXL1s"
BLYNK_TEMPLATE_NAME = "Quickstart Template"
BLYNK_AUTH_TOKEN = "NKV7_l21Ch2v0buSwwvqLU0zDpwA2dEP"

MIN_STEP_DELAY = 8
MAX_STEP_DELAY = 30

stepper_state = 1

generate = True
was_generating = True

#########################################################################################
################################### PIN DEFINITIONS #####################################
#########################################################################################

killswitch = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_UP)
generate_button = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_UP)

LED1 = machine.Pin(21, machine.Pin.OUT, machine.Pin.PULL_DOWN)
LED2 = machine.Pin(20, machine.Pin.OUT, machine.Pin.PULL_DOWN)
LED3 = machine.Pin(19, machine.Pin.OUT, machine.Pin.PULL_DOWN)
LED4 = machine.Pin(18, machine.Pin.OUT, machine.Pin.PULL_DOWN)

ENA = machine.Pin(0, machine.Pin.OUT)
ENB = machine.Pin(1, machine.Pin.OUT)
IN1 = machine.Pin(2, machine.Pin.OUT)
IN2 = machine.Pin(3, machine.Pin.OUT)
IN3 = machine.Pin(4, machine.Pin.OUT)
IN4 = machine.Pin(5, machine.Pin.OUT)

RELAY1 = machine.Pin(14, machine.Pin.OUT)
RELAY2 = machine.Pin(15, machine.Pin.OUT)

# set up ADC0 to read the capacitor voltage (the generator circuit output voltage)
adc0 = machine.ADC(machine.Pin(26))

#########################################################################################
###################################### FUNCTIONS ########################################
#########################################################################################

def show_on_LEDs(list):
    LED1.value(list[0])
    LED2.value(list[1])
    LED3.value(list[2])
    LED4.value(list[3])

def send_stepper_signal(list):
    ENA.value(list[0])
    IN1.value(list[1])
    IN2.value(list[2])
    ENB.value(list[3])
    IN3.value(list[4])
    IN4.value(list[5])
    show_on_LEDs([list[1], list[2], list[4], list[5]])

def move_stepper(steps = 200, CW = True, delay = MIN_STEP_DELAY):

    global generate
    global stepper_state

    for step in range(steps):

        if generate is True:
            return False

        if CW is True:
            stepper_state = stepper_state + 1
            if stepper_state > 4:
                stepper_state = 1
        elif CW is False:
            stepper_state = stepper_state - 1
            if stepper_state < 1:
                stepper_state = 4
        else:
            raise Exception("CW case error: {}".format(CW))

        if stepper_state is 1:
            send_stepper_signal([1, 1, 0, 1, 1, 0])
        elif stepper_state is 2:
            send_stepper_signal([1, 0, 1, 1, 1, 0])
        elif stepper_state is 3:
            send_stepper_signal([1, 0, 1, 1, 0, 1])
        elif stepper_state is 4:
            send_stepper_signal([1, 1, 0, 1, 0, 1])
        else:
            raise Exception("stepper_state case error: {}".format(stepper_state))

        utime.sleep_ms(delay)

    return True

def generator_disable():
    RELAY1.value(1)
    RELAY2.value(1)
    print("generator disabled")

def generator_enable():
    RELAY1.value(0)
    RELAY2.value(0)
    print("generator enabled")

def stepper_disable():
    send_stepper_signal([0, 0, 0, 0, 0, 0])
    print("stepper disabled")

def flash_LEDs(times = 1):
    for x in range(times):
        show_on_LEDs([1, 1, 1, 1])
        utime.sleep_ms(100)
        show_on_LEDs([0, 0, 0, 0])
        utime.sleep_ms(100)

#########################################################################################
##################################### INTERRUPTS ########################################
#########################################################################################

# this parameter definition has to be like this bc we call this function manually later
def killswitch_handler(killswitch = killswitch):
    print("kill switch triggered, disabling system...")
    stepper_disable()
    generator_disable()
    while True:
        flash_LEDs(1)

def generate_handler(generate_button):
    global generate
    global was_generating
    print("generate button pressed, switching modes...")
    if generate_button is False:
        while generate_button is False:
            pass
        utime.sleep_ms(30)

        if generate is True:
            generate = False
        elif generate is False:
            generate = True
        else:
            raise Exception("generate case error on button switch: {}".format(generate))

        handle_generate_state_change()

killswitch.irq(trigger = machine.Pin.IRQ_FALLING, handler = killswitch_handler)
generate_button.irq(trigger = machine.Pin.IRQ_FALLING, handler = generate_handler)

#########################################################################################
#################################### SET UP SYSTEM ######################################
#########################################################################################

print("disabling generator to communicate with stepper...")
generator_disable()
utime.sleep_ms(100)
print("disabling stepper...")
stepper_disable()
utime.sleep_ms(100)
print("enabling generator...")
generator_enable()

print()
print("hardware setup complete")
print()

flash_LEDs(2)

#########################################################################################
################################# CONNECT TO INTERNET ###################################
#########################################################################################

sta_if = network.WLAN(network.STA_IF)

def connect_to_network():
    print('connecting to network...')
    sta_if.active(True)
    #sta_if.connect('the Groove Machine', 'wiggles101') # ben's phone
    #sta_if.connect("Liams Iphone XR", 'colemansgimp')  # liam's phone
    #sta_if.connect('Lee', 'leeroijenkins')             # sam's phone
    sta_if.connect('SHAW-E8C2', 'breezy2116fever')     # home network
    while not sta_if.isconnected():
        pass
    print("network connected!")
    print('network configuration:', sta_if.ifconfig())
    print()
    flash_LEDs(2)

connect_to_network()

#########################################################################################
############################## INITIALIZE BLYNK INSTANCE ################################
#########################################################################################

print("Initializing Blynk instance...")
blynk = BlynkLib.Blynk(BLYNK_AUTH_TOKEN, insecure=True)

#########################################################################################
################# HANDLERS FOR COMMANDS COMING FROM THE BLYNK DASHBOARD #################
#########################################################################################

# handle the kill switch
@blynk.on("V2")
def v2_write_handler(value):
    if value[0] is "1":
        killswitch_handler()
    elif value[0] is "0":
        print("killswitch reset detected")
    else:
        raise Exception("kill case error on Blynk switch: {}".format(value[0]))

# handle the generate switch
@blynk.on("V0")
def v0_write_handler(value):
    global generate

    if value[0] is "0":
        generate = False
    elif value[0] is "1":
        generate = True
    else:
        raise Exception("generate case error on Blynk switch: {}".format(value[0]))

    handle_generate_state_change()

@blynk.on("connected")
def blynk_connected():
    print("Blynk server connected!")
    print("Updating Blynk server...")
    if generate is True:
        blynk.virtual_write(0, 1)
    if generate is False:
        blynk.virtual_write(0, 0)
    send_ADC0()
    blynk.virtual_write(2, 0)
    print("Blynk server update complete. Starting system...")
    print()

#########################################################################################
################# HANDLERS FOR DATA TRANSMITTING TO THE BLYNK DASHBOARD #################
#########################################################################################

# function to call when updating the generator voltage label
def send_ADC0():
    sensorData = adc0.read_u16()/65535
    sendValue = 15*sensorData
    print("ADC0: {d:.6f}, sending voltage: {v:2.4f}".format(d=sensorData, v=sendValue))
    blynk.virtual_write(1, sendValue)

# called in generate button interrupt, deals with setting up the system after a
# change mode command is recieved / created
def handle_generate_state_change():
    global generate
    global was_generating
    print()
    if generate is False:
        print("switching to motor mode...")
        was_generating = True
        blynk.virtual_write(0, 0)
    elif generate is True:
        print("switching to generate mode...")
        stepper_disable()
        generator_enable()
        blynk.virtual_write(0, 1)
    print()

#########################################################################################
###################### SET UP BLYNK TIMER FOR PERIODIC EXECUTIONS #######################
#########################################################################################

timer = BlynkTimer.BlynkTimer()
timer.set_interval(5, send_ADC0)

#########################################################################################
###################################### MAIN LOOP ########################################
#########################################################################################

while True:

    # make sure Pico is connected to the internet
    if not sta_if.isconnected():
        connect_to_network()

    if generate is False:

        if was_generating is True:
            generator_disable()
            was_generating = False
            print("calibrating motor...")
            move_stepper(20, True, MAX_STEP_DELAY)
            print("calibration complete")
            print()
            utime.sleep_ms(1000)

        move_stepper(100, True, MIN_STEP_DELAY)

        utime.sleep_ms(1000)

        move_stepper(100, False, MIN_STEP_DELAY)

        utime.sleep_ms(1000)

    # Blynk functions - need to be constantly re-called
    blynk.run()
    timer.run()
