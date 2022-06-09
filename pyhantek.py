import array
import time

import matplotlib.pyplot as plt
import numpy as np
import usb.core
import PIL

from hantek_protocol import *

class oscilloscope_channel:
    def __init__(self, channel, system_status):
               
        self.name = channel + 1
        self.state = OFF_ON[system_status[4 + channel * 10]]
        self.probetype = PROBETYPE[system_status[9 + channel * 10]]
        self.volts_per_div = VOLTS_PER_DIV[system_status[5 + channel * 10]] * self.probetype
        self.volts_per_div_unit = VOLTS_PER_DIV_UNIT[
            system_status[5 + channel * 10]
        ]
        self.coupling = COUPLING[system_status[6 + channel * 10]]
        self.bandwidth_filter = OFF_ON[system_status[7 + channel * 10]]
        self.tuning = VOLTS_PER_DIV_TUNING[system_status[8 + channel * 10]]
        self.phase = PHASE[system_status[10 + channel * 10]]
        self.volts_per_div_fine = system_status[11 + channel * 10]
        self.voltage_scale = 1 / 25 * self.volts_per_div 
        self.voltage_offset = (
            self.vertical_position(channel, system_status)
            / 25
            *self.volts_per_div
        )

    def vertical_position(self, channel, system_status):
        
        position = int.from_bytes(
            system_status[12 + channel * 10 : 14 + channel * 10],
            byteorder="little",
        )
        if system_status[13 + channel * 10] not in [0x00, 0x01]:
            position -= -65536

        return position

class DSO1062D:
    def __init__(self):

        self.osc = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if self.osc == None:
            raise ValueError("Device not found")
        self.osc.set_configuration()
        usb.util.claim_interface(self.osc, 0)

        self._oscilloscope_settings()

    def _oscilloscope_settings(self):
        
        self.SYSTEM_STATUS = self.ReadSettings()
        self.CH1 = oscilloscope_channel(0, self.SYSTEM_STATUS)
        self.CH2 = oscilloscope_channel(1, self.SYSTEM_STATUS)
        self._CHANNEL_DICT = {1: self.CH1, 2: self.CH2}
        self.timebase = TIMEBASE_VALUE[self.SYSTEM_STATUS[165]]
        self.timebase_unit = TIMEBASE_UNIT[self.SYSTEM_STATUS[165]]
        self.time_offset = self._horizontal_position(self.SYSTEM_STATUS)
    
    def _horizontal_position(self, system_status):

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

        position = round(self._convert_time_unit(position, self.timebase_unit), 4)

        return position

    def _convert_time_unit(self, value, unit):
        TIME_UNITS = {"ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1}
        return value /TIME_UNITS[unit] *1e-12

    def release(self):
        usb.util.dispose_resources(self.osc)
        
    def _SendCommand( self, origin, cmd, data, isDebug=False ):
        assert isinstance( data, array.array ), '\'data\' must be array.array(\'B\')'

        #time.sleep( 0.1 )
        action = 0x43 if isDebug else 0x53
        packetLen = 1 + len( data ) + 1
        packet = array.array( 'B', [ action, packetLen & 0xFF, ( packetLen >> 8 ) & 0xFF, cmd ] ) + data
        packet = packet + array.array( 'B', [ sum( packet ) & 0xFF ] )
        self.osc.write( 0x02, packet )
        return packet

    def _ReadAnswer( self, origin, rcode ):
        r = None
        while( True ):
            r = self.osc.read( 0x81, 1024*1024, 50)
            chksum = sum( r[:-1] ) & 0xFF
            if( chksum != r[-1] ):
                print("Bad Checksum")
            if( r[3] == rcode ):
                break
            else:
                print("Bad Answer")
        return r

    def Echo( self, data ):
        data = array.array( 'B', data )
        self._SendCommand( 'Echo', 0x00, data )
        r = self._ReadAnswer( 'Echo', 0x80 )
        return list( r[4:-1] )

    def ReadSettings( self ):
        self._SendCommand( 'ReadSettings', 0x01, array.array( 'B' ) )
        r = self._ReadAnswer( 'ReadSettings', 0x81 )
        return r

    def ReadSampleData( self, channel ):
        
        
        if getattr(self, f"CH{channel}").state == "Off":
            return None
        channel = channel -1
        while True:
            try:
                self._SendCommand( 'ReadSampleData', 0x02, array.array( 'B', [ 0x01, channel & 0x01 ] ) )
                r = array.array( 'B' )
                sdlen = 0
                while( True ):
                    d = self._ReadAnswer( 'ReadSampleData', 0x82 )
                    if( d[4] == 0x00 ):
                        sdlen = d[5] + (d[6]<<8) + (d[7]<<16)
                    elif( d[4] == 0x01 ):
                        r = r + d[6:-1]
                    elif( d[4] == 0x02 ):
                        break;
                break
            except Exception:
                pass
                
        return r
    
    def ReadScaledSampleData(self, channel=1):
        def center_and_scale_data_around_zero(sample_data, channel):

            centered_data = []

            for i in sample_data:
                if i > 127:
                    centered_data += [i - 256]
                    continue
                centered_data += [i]
            channel = self._CHANNEL_DICT[channel]
            scale = channel.voltage_scale
            offset = channel.voltage_offset

            return [i * scale + offset for i in centered_data]

        def create_timescale(sample_data):
            maximum = self.timebase / 400 * len(sample_data)
            times = np.linspace(-2 * maximum, 0, len(sample_data))
            times += maximum
            times -= self.time_offset

            return times

        self.Update()

        self.StartAcquisition()
            
        data = self.ReadSampleData(channel)
        if data != None:
            times = create_timescale(data)
            scaled_data = center_and_scale_data_around_zero(data, channel)
    
            return times, scaled_data
    
    def GraphSampleData(self, channel):
        
        try:
            x, y = self.ReadScaledSampleData(channel)
        except Exception as e:
            print(e)
            print(f"Channel {channel} is not active!")
            return
        fig, ax = plt.subplots(1, 1)
        fig.set_size_inches(8, 4)
        fig.set_dpi(150)
        ax.invert_xaxis()
        ax.grid()
        channel = self._CHANNEL_DICT[channel]
        ax.set_xlabel(f"Time in {self.timebase_unit}")
        ax.set_ylabel(f"Voltage in {channel.volts_per_div_unit}")
        ax.plot(x, y, ms=0.05, color="black")
        plt.show()
        return

    def Update(self):
        self._oscilloscope_settings()
        time.sleep(0.15)

    def LockControlPanel( self ):
        self._SendCommand( 'LockControlPanel', 0x12, array.array( 'B', [ 0x01, 0x01 ] ) )
        r = self._ReadAnswer( 'LockControlPanel', 0x92 )

    def UnLockControlPanel( self ):
        self._SendCommand( 'UnLockControlPanel', 0x12, array.array( 'B', [ 0x01, 0x00 ] ) )
        r = self._ReadAnswer( 'UnLockControlPanel', 0x92 )

    def StartAcquisition( self ):
        self._SendCommand( 'StartAcquisition', 0x12, array.array( 'B', [ 0x00, 0x00 ] ) )
        r = self._ReadAnswer( 'StartAcquisition', 0x92 )

    def StopAcquisition( self ):
        self._SendCommand( 'StopAcquisition', 0x12, array.array( 'B', [ 0x00, 0x01 ] ) )
        r = self._ReadAnswer( 'StopAcquisition', 0x92 )

    def Screenshot( self ):
        self._SendCommand( 'Screenshot', 0x20, array.array( 'B' ) )
        bmp = array.array( 'B' )
        while( True ):
            d = self._ReadAnswer( 'Screenshot', 0xA0 )
            if( d[4] == 0x01 ):
                bmp = bmp + d[5:-1]
            else:
                break;
        img = PIL.ImageChops.invert(PIL.Image.fromarray(np.frombuffer(bytearray(bmp), dtype=np.uint16).reshape(480, 800)))
        return img

    def ReadSystemTime( self ):
        self._SendCommand( 'ReadSystemTime', 0x21, array.array( 'B' ) )
        r = self._ReadAnswer( 'ReadSystemTime', 0xA1 )
        r = '%04d-%02d-%02d %02d:%02d:%02d' % ( r[5]*0xFF + r[4] + 7, r[6], r[7], r[8], r[9], r[10] )
        return r
