import time
from enum import Enum, auto

import RPi.GPIO as GPIO
import smbus

from .format import NumberFormat, unsigned, signed
from .read_data import ReadData


class SensorAddress(Enum):
    OPEN = 0x71
    CLOSED = 0x70


class Mode(Enum):
    STANDBY = auto()
    CYCLE = auto()


class CycleInterval(Enum):
    T_3_S: 0
    T_100_S: 1
    T_300_S: 2


class AQIValue(Enum):
    GOOD = 49
    ACCEPTABLE = 99
    SUBSTANDARD = 149
    POOR = 199
    BAD = 299
    VERY_BAD = 499

    @staticmethod
    def interpret(value):
        for e in AQIValue:
            if e.value <= value:
                return e


class AQIAccuracy(Enum):
    INVALID = 0,
    LOW = 1,
    MEDIUM = 2,
    HIGH = 3


class IntType(Enum):
    LATCH = 0
    COMPARATOR = 1


class IntPolarity(Enum):
    POSITIVE = 0
    NEGATIVE = 1


class SoundStability(Enum):
    UNSTABLE = 0,
    STABLE = 1


class ParticleValidity(Enum):
    INVALID = 0,
    VALID = 1


class ParticleSensor(Enum):
    def __new__(cls, value, unit):
        obj = bytes.__new__(cls, [value])
        obj._value_ = value
        obj.unit = unit
        return obj

    PPD42 = (1, 'ppL')
    SDS011 = (2, 'ug/m3')


# Settings registers
PARTICLE_SENSOR_SELECT_REG = 0x07
LIGHT_INTERRUPT_ENABLE_REG = 0x81
LIGHT_INTERRUPT_THRESHOLD_REG = 0x82
LIGHT_INTERRUPT_TYPE_REG = 0x83
LIGHT_INTERRUPT_POLARITY_REG = 0x84
SOUND_INTERRUPT_ENABLE_REG = 0x85
SOUND_INTERRUPT_THRESHOLD_REG = 0x86
SOUND_INTERRUPT_TYPE_REG = 0x87
CYCLE_TIME_PERIOD_REG = 0x89

# Executable commands
ON_DEMAND_MEASURE_CMD = 0xE1
RESET_CMD = 0xE2
CYCLE_MODE_CMD = 0xE4
STANDBY_MODE_CMD = 0xE5
LIGHT_INTERRUPT_CLR_CMD = 0xE6
SOUND_INTERRUPT_CLR_CMD = 0xE7

# Read data for whole categories
AIR_DATA_READ = 0x10
AIR_DATA_BYTES = 12
AIR_QUALITY_DATA_READ = 0x11
AIR_QUALITY_DATA_BYTES = 10
LIGHT_DATA_READ = 0x12
LIGHT_DATA_BYTES = 5
SOUND_DATA_READ = 0x13
SOUND_DATA_BYTES = 18
SOUND_FREQ_BANDS = 6
PARTICLE_DATA_READ = 0x14
PARTICLE_DATA_BYTES = 6


class Sensor:
    def __init__(self, address=SensorAddress.OPEN, ready_pin=11, light_int_pin=7, sound_int_pin=8):
        self.address = address
        self.ready_pin = ready_pin

        self.light_int_pin = light_int_pin
        self.sound_int_pin = sound_int_pin

        self._init_hw()
        self.reset()

    # utility

    def _init_hw(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.ready_pin, GPIO.IN)

        if self.light_int_pin is not None:
            GPIO.setup(self.light_int_pin, GPIO.IN)
        if self.sound_int_pin is not None:
            GPIO.setup(self.sound_int_pin, GPIO.IN)

        self.i2c = smbus.SMBus(1)  # Port 1 is the default for I2C on Raspberry Pi

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        GPIO.cleanup()

    def _command(self, command):
        self.i2c.write_byte(self.address.value, command)
        time.sleep(0.006)

    def _set(self, reg, fmt: NumberFormat, value):
        self.i2c.write_i2c_block_data(self.address.value, reg, fmt.write(value))
        time.sleep(0.006)

    def _get(self, reg, count):
        data = self.i2c.read_i2c_block_data(self.address.value, reg, count)
        return ReadData(data)

    # readiness

    def wait_for_ready(self):
        GPIO.wait_for_edge(self.ready_pin, GPIO.FALLING)

    def is_ready(self):
        return GPIO.input(self.ready_pin) == 0

    def was_ready(self):
        return GPIO.event_detected(self.ready_pin)

    # commands

    def measure(self):
        if self.mode != Mode.STANDBY:
            raise Exception("Can measure only in STANDBY mode.")
        self._command(ON_DEMAND_MEASURE_CMD)

    def reset(self):
        self._command(RESET_CMD)
        self.wait_for_ready()

        self.mode = Mode.STANDBY
        self.interval = CycleInterval.T_3_S
        GPIO.remove_event_detect(self.ready_pin)

        self.light_int = False
        self.light_int_type = IntType.LATCH
        self.light_int_polarity = IntPolarity.POSITIVE
        self.light_int_threshold = 0
        if self.light_int_pin:
            GPIO.remove_event_detect(self.light_int_pin)

        self.sound_int = False
        self.sound_int_type = IntType.LATCH
        self.sound_int_threshold = 0
        if self.sound_int_pin:
            GPIO.remove_event_detect(self.sound_int_pin)

        self.particle_sensor = None

    def cycle(self, interval: CycleInterval):
        if self.mode == Mode.CYCLE:
            if self.interval == interval:
                return
            self.standby()
        if self.interval != interval:
            self._set(CYCLE_TIME_PERIOD_REG, unsigned(1), interval.value)
            self.interval = interval
        self._command(CYCLE_MODE_CMD)
        GPIO.add_event_detect(self.ready_pin, GPIO.FALLING)

    def standby(self):
        if self.mode != Mode.STANDBY:
            GPIO.remove_event_detect(self.ready_pin)
            self._command(STANDBY_MODE_CMD)
            self.wait_for_ready()

    # light interrupts

    def enable_light_int(self, type: IntType, polarity: IntPolarity, threshold):
        if self.light_int_pin is None:
            raise Exception("Light interrupt is not connected.")
        if self.light_int:
            if self.light_int_type == type and self.light_int_polarity == polarity and self.light_int_threshold == threshold:
                return
            self.disable_light_int()
        if self.light_int_type != type:
            self._set(LIGHT_INTERRUPT_TYPE_REG, unsigned(1), type.value)
            self.light_int_type = type
        if self.light_int_polarity != polarity:
            self._set(LIGHT_INTERRUPT_POLARITY_REG, unsigned(1), polarity.value)
            self.light_int_polarity = polarity
        if self.light_int_threshold != threshold:
            self._set(LIGHT_INTERRUPT_THRESHOLD_REG, unsigned(2, 2), threshold)
            self.light_int_threshold = threshold
        self._set(LIGHT_INTERRUPT_ENABLE_REG, unsigned(1), 1)
        GPIO.add_event_detect(self.light_int_pin, GPIO.FALLING)

    def disable_light_int(self):
        if self.light_int:
            self._set(LIGHT_INTERRUPT_ENABLE_REG, unsigned(1), 0)
            GPIO.remove_event_detect(self.light_int_pin)

    def clear_light_int(self):
        if self.light_int and self.light_int_type == IntType.LATCH:
            self._command(LIGHT_INTERRUPT_CLR_CMD)

    def is_light_int(self):
        if self.light_int:
            return GPIO.input(self.light_int) == 0
        return False

    def was_light_int(self):
        if self.light_int:
            return GPIO.event_detected(self.light_int_pin)
        return False

    # sound interrupts

    def enable_sound_int(self, type: IntType, threshold):
        if self.sound_int_pin is None:
            raise Exception("Sound interrupt is not connected.")
        if self.sound_int:
            if self.sound_int_type == type and self.sound_int_threshold == threshold:
                return
            self.disable_sound_int()
        if self.sound_int_type != type:
            self._set(SOUND_INTERRUPT_TYPE_REG, unsigned(1), type.value)
            self.sound_int_type = type
        if self.sound_int_threshold != threshold:
            self._set(SOUND_INTERRUPT_THRESHOLD_REG, unsigned(2, 0), threshold)
            self.sound_int_threshold = threshold
        self._set(SOUND_INTERRUPT_ENABLE_REG, unsigned(1), 1)
        GPIO.add_event_detect(self.sound_int, GPIO.FALLING)

    def disable_sound_int(self):
        if self.sound_int:
            self._set(SOUND_INTERRUPT_ENABLE_REG, unsigned(1), 0)
            GPIO.remove_event_detect(self.sound_int_pin)

    def clear_sound_int(self):
        if self.sound_int and self.sound_int_type == IntType.LATCH:
            self._command(SOUND_INTERRUPT_CLR_CMD)

    def is_sound_int(self):
        if self.sound_int:
            return GPIO.input(self.sound_int) == 0
        return False

    def was_sound_int(self):
        if self.sound_int:
            return GPIO.event_detected(self.sound_int_pin)
        return False

    # particle sensor

    def enable_particle_sensor(self, particle_sensor: ParticleSensor):
        if self.particle_sensor == particle_sensor:
            return
        self.disable_particle_sensor()
        self._set(PARTICLE_SENSOR_SELECT_REG, unsigned(1), self.particle_sensor.value)
        self.particle_sensor = particle_sensor

    def disable_particle_sensor(self):
        if self.particle_sensor is not None:
            self._set(PARTICLE_SENSOR_SELECT_REG, unsigned(1), 0)
            self.particle_sensor = None

    # reading

    def read_data(self, flatten: False):
        if flatten:
            return {
                **self.read_air_data(),
                **(self.read_air_quality_data() if self.mode == Mode.CYCLE else {}),
                **self.read_light_data(),
                **self.read_sound_data(True),
                **(self.read_particle_data() if self.particle_sensor is not None else {})
            }
        else:
            return dict([
                *('air', self.read_air_data()),
                *(('air_quality', self.read_air_quality_data()) if self.mode == Mode.CYCLE else ()),
                *('light', self.read_light_data()),
                *('sound', self.read_sound_data(False)),
                *(('particle', self.read_particle_data()) if self.particle_sensor is not None else {})
            ])

    def read_air_data(self):
        if not self.is_ready():
            raise Exception("Not ready")
        data = self._get(AIR_DATA_READ, AIR_DATA_BYTES)
        return {
            'T_C': data.single(signed(1, 1)),
            'P_Pa': data.single(unsigned(4)),
            'H_pc': data.single(unsigned(1, 2)),
            'G_ohm': data.single(unsigned(4))
        }

    def read_air_quality_data(self):
        if not self.is_ready():
            raise Exception("Not ready")
        data = self._get(AIR_QUALITY_DATA_READ, AIR_QUALITY_DATA_BYTES)
        aqi = data.single(unsigned(2, 1))
        return {
            'AQI': aqi,
            'AQI_value': AQIValue.interpret(aqi),
            'CO2e': data.single(unsigned(2, 1)),
            'bVOC': data.single(unsigned(2, 2)),
            'AQI_accuracy': data.enum(AQIAccuracy)
        }

    def read_light_data(self):
        if not self.is_ready():
            raise Exception("Not ready")
        data = self._get(LIGHT_DATA_READ, LIGHT_DATA_BYTES)
        return {
            'illum_lux': data.single(unsigned(2, 2)),
            'white': data.single(unsigned(2))
        }

    def read_sound_data(self, flatten=False):
        if not self.is_ready():
            raise Exception("Not ready")
        data = self._get(SOUND_DATA_READ, SOUND_DATA_BYTES)
        return {
            'SPL_dBA': data.single(unsigned(1, 1)),
            **Sensor._read_sound_bands(data, flatten),
            'peak_amp_mPa': data.single(unsigned(2, 2)),
            'stable': data.enum(SoundStability)
        }

    @staticmethod
    def _read_sound_bands(data: ReadData, flatten: bool):
        bands = data.striped(unsigned(1, 1), SOUND_FREQ_BANDS)
        if flatten:
            return dict(
                ('SPL_bands_dB_{}'.format(i + 1), b)
                for (i, b) in enumerate(bands)
            )
        else:
            return {'SPL_bands_dB': bands},

    def read_particle_data(self):
        if self.particle_sensor is None:
            raise Exception("No particle sensor")
        if not self.is_ready():
            raise Exception("Not ready")
        data = self._get(PARTICLE_DATA_READ, PARTICLE_DATA_BYTES)
        return {
            'duty_cycle_pc': data.single(unsigned(1, 2)),
            'concentration': data.single(unsigned(2, 2)),
            'conc_unit': self.particle_sensor.unit,
            'valid': data.enum(ParticleValidity)
        }
