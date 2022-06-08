import array
import time

import matplotlib.pyplot as plt
import numpy as np
import usb.core

from hantek_protocol import *


class DSO1062D:
    def __init__(self):

        self.osc = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if self.osc == None:
            raise ValueError("Device not found")
        self.osc.set_configuration()
        usb.util.claim_interface(self.osc, 0)

        self.settings = self.oscilloscope_settings()

    class oscilloscope_settings:
        def __init__(self):

            self.SYSTEM_STATUS = self.send_command("S\x02\x00\x01V")
            self.CH1 = self.oscilloscope_channel(0, self.SYSTEM_STATUS)
            self.CH2 = self.oscilloscope_channel(1, self.SYSTEM_STATUS)
            self.CHANNEL_DICT = {1: self.CH1, 2: self.CH2}
            self.timebase = TIMEBASE_VALUE[self.SYSTEM_STATUS[165]]
            self.timebase_unit = TIMEBASE_UNIT[self.SYSTEM_STATUS[166]]
            self.time_offset = self.horizontal_position(self.SYSTEM_STATUS)

        def horizontal_position(self, system_status):

            position = int.from_bytes(system_status[167:175], byteorder="little")
            if (
                position
                > int.from_bytes(
                    [255, 255, 255, 255, 255, 255, 255, 255], byteorder="little"
                )
                // 2
            ):
                position -= int.from_bytes(
                    [255, 255, 255, 255, 255, 255, 255, 255], byteorder="little"
                )

            position = round(self.convert_time_unit(position, self.timebase_unit), 4)

            return position

        def convert_time_unit(self, value, unit):
            TIME_UNITS = {"ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1}
            return value * TIME_UNITS[unit] / 1e-12

        class oscilloscope_channel:
            def __init__(self, channel, system_status):

                self.name = channel + 1
                self.state = OFF_ON[system_status[4 + channel * 10]]
                self.volts_per_div = VOLTS_PER_DIV[system_status[5 + channel * 10]]
                self.volts_per_div_unit = VOLTS_PER_DIV_UNIT[
                    system_status[5 + channel * 10]
                ]
                self.coupling = COUPLING[system_status[6 + channel * 10]]
                self.bandwidth_filter = OFF_ON[system_status[7 + channel * 10]]
                self.tuning = VOLTS_PER_DIV_TUNING[system_status[8 + channel * 10]]
                self.probetype = PROBETYPE[system_status[9 + channel * 10]]
                self.phase = PHASE[system_status[10 + channel * 10]]
                self.volts_per_div_fine = system_status[11 + channel * 10]
                self.voltage_scale = 10 / 25 * self.volts_per_div
                self.voltage_offset = (
                    self.vertical_position(channel, system_status)
                    / 25
                    * self.volts_per_div
                )

            def vertical_position(self, channel, system_status):

                position = int.frombytes(
                    system_status[12 + channel * 10, 14 + channel * 10],
                    byteorder="little",
                )
                if system_status[13 + channel * 10] not in [0x00, 0x01]:
                    position -= -65536

                return position

    def send_command(self, command):
        self.osc.write(0x2, command)

    def recieve_response(self):
        return self.osc.read(0x81, 10000)

    def start_acquisition(self):
        self.send_command("S\x04\x00\x12\x00\x00i")

    def stop_acquisition(self):
        self.send_command("S\x04\x00\x12\x00\x01j")

    def read_sample_data(self, channel=1, scale=True):
        def center_and_scale_data_around_zero(sample_data, channel):

            centered_data = []

            for i in sample_data:
                if i > 127:
                    centered_data += [i - 256]
                    continue
                centered_data += [i]

            scale = channel.voltage_scale
            offset = channel.voltage_offset

            return [i * scale + offset for i in centered_data]

        def create_timescale(sample_data, channel):
            maximum = self.timebase / 400 * len(sample_data)
            times = np.linspace(-2 * maximum, 0, len(sample_data))
            times += maximum
            times -= self.time_offset

            return times

        channel = self.settings.CHANNEL_DICT[channel]

        self.start_acquisition()
        self.update()
        self.send_command(
            f"S\x04\x00\x02\x01{CHANNEL[channel.name]}{CHANNEL_CHECKSUM[channel.name]}"
        )
        response = []
        packets = 0
        while packets < 3:
            response += self.recieve_response()

        data = response[15:-8]

        if scale == False:
            return data

        else:
            times = create_timescale(data, channel)
            scaled_data = center_and_scale_data_around_zero(data, channel)

            return times, scaled_data

    def screenshot(self):
        def _ReadAnswer(self, rcode):
            r = None
            while True:
                r = self.osc.read(0x81, 1024 * 1024, 500)
                chksum = sum(r[:-1]) & 0xFF
                if chksum != r[-1]:
                    print("BADCHKSM")
                if r[3] == rcode:
                    break
                else:
                    print("BADANSWER")
            return r

        self.send_command("S\x02\x00 u")
        bmp = array.array("B")
        while True:
            d = _ReadAnswer(0xA0)
            if d[4] == 0x01:
                bmp = bmp + d[5:-1]
            else:
                break
        img = np.frombuffer(bytearray(bmp), dtype=np.uint16).reshape(480, 800)
        img = img.astype(np.uint8)
        plt.imshow(img, interpolation="nearest")
        plt.show()
        return img

    def plot(self, channel):

        x, y = self.read_sample_data(channel)
        fig, ax = plt.subplots(1, 1)
        fig.set_size_inches(8, 4)
        fig.set_dpi(150)
        ax.invert_xaxis()
        ax.grid()
        ax.set_xlabel(f"Time in {self.timebase_unit}")
        ax.set_ylabel(f"VOltage in {channel.volts_per_div_unit}")
        ax.plot(x, y, ms=0.05, color="black")
        plt.show()
        return

    def update(self):
        self.settings.__init__()
        time.sleep(0.25)
