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
####################################### DEFINES #########################################
#########################################################################################

#### Blynk globals ####

BLYNK_TEMPLATE_ID = "TMPL2UsApXL1s"
BLYNK_TEMPLATE_NAME = "Quickstart Template"
BLYNK_AUTH_TOKEN = "NKV7_l21Ch2v0buSwwvqLU0zDpwA2dEP"

GENERATE_SWITCH_VPIN = 0
POWER_VPIN = 1
KILLSWITCH_VPIN = 2

BLYNK_UPDATE_INTERVAL = 5 # seconds

#### ADC globals ####
ADC_UPDATE_INTERVAL = 10 # milliseconds
N_adc_samples = 1 # number of ADC samples since last blynk update
adc0_sum = 0 # sum of ADC samples for averaging
adc1_sum = 0

#### WiFi Stuff ####

WIFI_NAME = 'SHAW-E8C2'

known_wifi_passwords = {
	'the Groove Machine': 'wiggles101', # ben's phone
	'Liams Iphone XR': 'colemansgimp',  # liam's phone
	'Lee': 'leeroijenkins',             # sam's phone
	'SHAW-E8C2': 'breezy2116fever'      # home network
}

#### Stepper Stuff ####

MIN_STEP_DELAY = 8
MAX_STEP_DELAY = 20

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

# set up ADC0 to read voltage from amplifiers and ADC1 to read current from amplifiers
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

def show_on_LEDs(list):
	LED1.value(list[3])
	LED2.value(list[2])
	LED3.value(list[1])
	LED4.value(list[0])

def send_stepper_signal(list):
	ENA.value(list[0])
	IN1.value(list[1])
	IN2.value(list[2])
	ENB.value(list[3])
	IN3.value(list[4])
	IN4.value(list[5])
	show_on_LEDs([list[1], list[2], list[4], list[5]])

def disable_generator():
	RELAY1.value(0)
	RELAY2.value(1)
	print("generator disabled")

def enable_generator():
	RELAY1.value(1)
	RELAY2.value(0)
	print("generator enabled")

def disable_stepper():
	send_stepper_signal([0, 0, 0, 0, 0, 0])
	print("stepper disabled")

def brake_stepper():
	send_stepper_signal([1, 0, 0, 1, 0, 0])
	print("stepper braked")

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

def connect_to_WiFi_network(ssid = 'SHAW-E8C2'):
	sta_if = network.WLAN(network.STA_IF)
	print('connecting to WiFi network "{}"...'.format(WIFI_NAME))
	sta_if.active(True)
	try:
		sta_if.connect(ssid, known_wifi_passwords[ssid])
	except:
		print("WIFI CONNECTION ERROR - CHECK NETWORK NAME OR PASSWORD")
	while not sta_if.isconnected():
		print(sta_if.status())
		sweep_LEDs(5)
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

#########################################################################################
##################################### INTERRUPTS ########################################
#########################################################################################

# deals with killswitch button trigger
def killswitch_handler():
	global kill
	killswitch_pause()
	kill = False if kill is True else True
	handle_kill_state_change()

# deals with generate button trigger
def generate_handler():
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
blynk_instance = BlynkLib.Blynk(BLYNK_AUTH_TOKEN, insecure = True)

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

# updates the power label on the dashboard
def update_dashboard_power():

	if N_adc_samples is 0:
		print("ADC averaging incomplete - dashboard not updated\n")
	else:
		global generate
		global N_adc_samples
		global adc0_sum
		global adc1_sum

		adc0_output_avg = adc0_sum/N_adc_samples
		adc1_output_avg = adc1_sum/N_adc_samples
		adc0_sum = 0
		adc1_sum = 0
		N_adc_samples = 0

		if generate is True:
			voltage = 4*3.3*adc1_output_avg
			current = (3.3/(0.55 *100))*adc0_output_avg
			print("GENERATOR:")
		else:
			voltage = 4*3.3*adc1_output_avg
			current = (3.3/(0.5*10))*adc0_output_avg
			print("MOTOR:")

		print("ADC0: {d:.6f}, voltage: {v:2.4f} V  ".format(d=adc1_output_avg, v=voltage))
		print("ADC1: {d:.6f}, current: {c:2.4f} mA".format(d=adc0_output_avg, c=current*1000))
		print("{n:2.4f} samples averaged\n" .format(n=N_adc_samples))
		blynk_instance.virtual_write(POWER_VPIN, voltage*current)

# samples the ADC to ensure value sent to dashboard is averaged
def sample_adcs():
	global N_adc_samples
	global adc0_sum
	global adc1_sum

	adc0_sum = adc0_sum + adc0.read_u16()/65535
	adc1_sum = adc1_sum + adc1.read_u16()/65535

	N_adc_samples = N_adc_samples + 1

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
		initialize_hardware()
		generate = True
		was_generating = True

# sets up the system after a generate / drive command is recieved / created
def handle_generate_state_change():
	global generate
	global was_generating
	blynk_instance.virtual_write(GENERATE_SWITCH_VPIN, 1 if generate is True else 0)
	if generate is False:
		print("\nswitching to motor mode...\n")
		was_generating = True
	elif generate is True:
		print("\nswitching to generate mode...\n")
		disable_stepper()
		utime.sleep_ms(100)
		enable_generator()
		utime.sleep_ms(100)
		print()

# SET UP BLYNK TIMER FOR PERIODIC EXECUTIONS

blynk_update_timer = BlynkTimer.BlynkTimer()
blynk_update_timer.set_interval(BLYNK_UPDATE_INTERVAL, update_dashboard_power)

#SET UP HARDWARE TIMER TO EXECTUE ADC AVERAGING PERIODICALLY

ADC_timer = machine.Timer(period=ADC_UPDATE_INTERVAL, mode=machine.Timer.PERIODIC, callback=sample_adcs)

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
		if generate is False:
			if was_generating is True:
				disable_generator()
				was_generating = False
				print("calibrating motor...")
				move_stepper(23, True, MAX_STEP_DELAY)
				print("calibration complete! resetting...\n")
				utime.sleep_ms(500)
				move_stepper(18, False, MIN_STEP_DELAY)
				utime.sleep_ms(1000)
			move_stepper(800, True, MIN_STEP_DELAY)
			brake_stepper()
			utime.sleep_ms(10000)
			move_stepper(800, False, MIN_STEP_DELAY)
			brake_stepper()
			utime.sleep_ms(10000)

	blynk_instance.run()
	blynk_update_timer.run()
