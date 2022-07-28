# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import os
import soundfile as sf
import sounddevice as sd
import time

import RPi.GPIO as GPIO
import numpy as np
from threading import Thread, Lock
from subprocess import call

'''
This code is the one used on the Raspberry Pi box (no gui)

'''



import logging
logger = logging.getLogger()


def get_GPIO_bool(trig_value, parralel_GPIO):
    bool_filter = np.array(np.array(list('{0:08b}'.format(trig_value))), dtype=bool)
    GPIO_trigOn = parralel_GPIO[bool_filter].tolist()
    return GPIO_trigOn


class sound_trig_Thread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.lock = Lock()
        self._running = False
        self.current = 0

    def set_params(self, playframe, stream, stim_folder, sound_dtype, config_GPIO):
        self.playframe = playframe
        self.stream = stream
        self.stim_folder = stim_folder
        self.sound_dtype = sound_dtype

        self.parralel_GPIO = config_GPIO['parralel']
        for i in self.parralel_GPIO:
            GPIO.setup(i.item(), GPIO.OUT)
            GPIO.output(i.item(), GPIO.LOW)

        self.LEDState_GPIO = config_GPIO['LED_State']

    def running(self):
        with self.lock:
            return self._running

    def run(self):
        with self.lock:
            self._running = True

        nb_items = self.playframe.shape[0]
        GPIO.output(self.LEDState_GPIO[0], GPIO.HIGH)
        Led1 = 0
        Led2 = 0
        Led3 = 0

        for index, row in self.playframe.iterrows():   #playframe.iloc[self.current:]
            if not self.running():
                self.current = index
                logger.info('Stopped at index ' + str(self.current))
                break

            if index > round(nb_items/4) and Led1 == 0:
                GPIO.output(self.LEDState_GPIO[1], GPIO.HIGH)
                Led1 = 1
            if index > round(nb_items/2) and Led2 == 0:
                GPIO.output(self.LEDState_GPIO[2], GPIO.HIGH)
                Led2 = 1
            if index > 3*round(nb_items/4) and Led3 == 0:
                GPIO.output(self.LEDState_GPIO[3], GPIO.HIGH)
                Led3 = 1

            logger.debug('index : ', index)
            sound_data, sample_rate = sf.read(self.stim_folder + row['Stimulus'] + '.wav')
            sound_data = sound_data.astype(self.sound_dtype)
            trig_value = row['Trigger']
            GPIO_trigOn = get_GPIO_bool(trig_value, self.parralel_GPIO)
            isi = round(row['ISI'] * 10**-3, 3)
            logger.info('Reading {}'.format(row['Stimulus']))

                       
            # Add 0 padding to improves sound quality (in cas of very short sounds)
            #padd_init = np.zeros((round(sample_rate*0.01), sound_data.shape[1]), dtype=self.sound_dtype) # add 10ms latency (constant)
            padd_end = np.zeros((round(sample_rate*0.05), sound_data.shape[1]), dtype=self.sound_dtype) # add 50ms -> removed from ISI
            isi -= 0.05
            sound_data = np.concatenate((sound_data, padd_end), axis=0)
            logger.info('with padding')

            #try:
            self.stream.start()
            GPIO.output(GPIO_trigOn,1)
            try:
                self.stream.write(sound_data)
                self.stream.stop()
            except sd.PortAudioError:
                logger.warning('catch Exception :')
                logger.warning(sd.PortAudioError)
                return


            GPIO.output(GPIO_trigOn, 0)
            logger.info('isi : ', isi)
            time.sleep(isi)

        GPIO.output(self.LEDState_GPIO[4], GPIO.HIGH)

    def stop(self):
        with self.lock:
            self._running = False
        self.stream.abort()


#TODO v0.3 : LOG + state graph
class PyAudio_protocol_rpi():

    config_GPIO = { 'mode':0,  #0 BOARD 1 BCM
            'parralel':np.array([32,18,36,37,16,33,23,21], dtype=np.int32), #Correspondance port // [9,8,7,...,2]
            #'parralel':np.array([29,31,33,35,37,36,38,40], dtype=np.int32) #basic rpi
            'butStart':7,
            'butStop':11,
            'LED_Start':22,
            'LED_State':[13,15,19,29,31]
    }

    def __init__(self, parent = None):
        #GPIO.setmode(GPIO.BOARD)
        self.sound_trig_Thread = sound_trig_Thread()
        self._running = False
        self._playing = False
        self.state = 'Init'
        logger.info('self.state : ', self.state)

    def set_config(self, playframe, num_device=5, stim_folder='', sample_rate=44100,
            channels=2, sound_dtype='float32'):
        '''
        '''
        self.playframe = playframe
        self.num_device = num_device
        self.stim_folder = stim_folder
        self.sample_rate = sample_rate
        self.channels = channels
        self.sound_dtype = sound_dtype
        self.stream = sd.OutputStream(device = num_device,
            samplerate = sample_rate, channels=channels, dtype=sound_dtype)

        if self.config_GPIO['mode'] == 0:
            GPIO.setmode(GPIO.BOARD)
        else:
            GPIO.setmode(GPIO.BCM)

        self.sound_trig_Thread.set_params(self.playframe,
            self.stream, self.stim_folder, self.sound_dtype, self.config_GPIO)

        GPIO.setup(self.config_GPIO['butStart'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.config_GPIO['butStop'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.config_GPIO['LED_Start'],GPIO.OUT)
        [GPIO.setup(ii,GPIO.OUT) for ii in self.config_GPIO['LED_State']]

        self.state = 'Config'
        logger.info('self.state : ', self.state)

    def running(self):
        return self._running

    def playing(self):
        return self._playing #could be a mutex ?

    def onStartButton(self, numGPIO):
        logger.debug('press start')
        if not self.playing():
            logger.debug('started')
            when_pressed = time.time()
            while GPIO.input(self.config_GPIO['butStart']):
                time.sleep(0.001)
                time_pressed = time.time() - when_pressed
                if time_pressed > 1:
                    self.sound_trig_Thread.start()
                    self._playing = True


    def onStopButton(self, numGPIO):
        logger.debug('Stopped')
        when_pressed = time.time()
        while GPIO.input(self.config_GPIO['butStop']):
            time.sleep(0.001)
        time_pressed = time.time() - when_pressed
        if time_pressed > 2:
            self.stop()
            return


    def start(self):
        GPIO.add_event_detect(self.config_GPIO['butStart'], GPIO.RISING)
        GPIO.add_event_detect(self.config_GPIO['butStop'], GPIO.RISING)
        GPIO.add_event_callback(self.config_GPIO['butStart'], self.onStartButton)
        GPIO.add_event_callback(self.config_GPIO['butStop'], self.onStopButton)

        self.state = 'Running : stim %i %s'.format('trucTODO')
        self._running = True
        logger.debug(self.state)
        GPIO.output(self.config_GPIO['LED_Start'],GPIO.HIGH)
        while self.running():
            time.sleep(0.5)

    def pause(self):
        #TODO v0.3
        pass

    def stop(self):
        '''
        In this case, we want stop button stops all the process and shutdown the rpi
        '''
        logger.debug('Stopping')
        GPIO.remove_event_detect(self.config_GPIO['butStart'])
        GPIO.remove_event_detect(self.config_GPIO['butStop'])
        GPIO.output(self.config_GPIO['LED_Start'],GPIO.LOW)
        self._running = False

        if self.playing():
            self.sound_trig_Thread.stop()
            self._playing = False
            [GPIO.output(ii,GPIO.LOW) for ii in self.config_GPIO['LED_State']]

        self.stream.close()

        logger.info('everything is closed, could shutdown rpi')
        #switch off the rpi
        call("sudo shutdown -h now", shell=True)

    def get_state(self):
        return self.state

    def save_results(self):
        #TODO v0.3
        pass



def test_audioproto():
        '''
        Test with playframe and stims given in examples folder.
        Should be run from core_rpi_nogui.py folder
        '''
        import pandas as pd

        proto = PyAudio_protocol()

        num_device = 5  # HifiBerry device
        playframe_csv = './../examples/playframe_ex1.csv'
        playframe = pd.read_csv(playframe_csv)
        stim_folder = './../examples/stims_ex/'
        sample_rate = 44100
        channels = 2
        sound_dtype='float32'

        proto.set_config(playframe, num_device, stim_folder, sample_rate, channels,
            sound_dtype)
        proto.start()



if __name__ == '__main__':

    test_audioproto()
