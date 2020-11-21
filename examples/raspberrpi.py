from video_backend import VideoBackEnd
import picamera
from picamera.array import PiRGBArray
from picamera.array import PiYUVArray
import numpy as np
import threading
import sys
from payload import Payload
import traceback
from time import sleep, time
import log
import logging
import numpy
import cv2

# Helper class implementing an IO deamon thread
class StartThreadToStream:

    def __init__(self, pub_socket):
        self.newpayload = False
        self.payload = None
        self.pub_socket = pub_socket
        self._stop = False
        self._thread = threading.Thread(target=self._run, args=())
        self._thread.daemon = True
        self._thread.start()
    
    def _run(self):
        while not self._stop:
            if self.newpayload == True:
                self.newpayload = False
                #f = self.payload[0][:,:,0]      # If only brightness information is needed from yuv format and not rgb 
                self.pub_socket.send(self.payload)
            else:
                sleep(0.0001)

    def dataready(self, payload):
        self.payload = payload
        self.newpayload = True

    def close(self):
        self._stop = True

ip = "192.168.0.188"    # ip address of remote pupil or localhost
port = "50020"      # same as in the pupil remote gui
device = "eye0"

# initialize the stream
backend = VideoBackEnd(ip, port)

def streamVideo():
    resolution =  (192, 192)
    framerate = 90
    pub_socket = backend.get_msg_streamer()
    # Make sure to set up raspberry pi camera
    # More information here: https://www.raspberrypi.org/documentation/configuration/camera.md
    with picamera.PiCamera() as camera:
        # sleep(2.0)  # Warmup time; needed by PiCamera on some RPi's
        # set camera parameters
        camera.resolution = resolution
        camera.framerate = framerate
        #rawCapture = PiRGBArray(camera, size=resolution)
        rawCapture = PiYUVArray(camera, size=resolution)
        stream = camera.capture_continuous(rawCapture, format="yuv", use_video_port=True)
        frame_counter_per_sec = 0
        frame_index = 1
        #streamimage = StartThreadToStream(pub_socket)
        payload = Payload(device, resolution[0], resolution[1], "gray")
        fps = 0
        start_time = time()
        try:
            for f in stream:
                if backend.is_publishable():
                    # grab the frame from the stream and clear the stream in
                    # preparation for the next frame
                    frame = f.array
                    #frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    frame = numpy.ascontiguousarray(frame[:,:,0])
                    payload.setPayloadParam(time(), frame, frame_index)
                    #streamimage.dataready(payload.get())    #   give it to StartThreadToStream to publish
                    pub_socket.send(payload.get())           #   publish here
                    seconds = time() - start_time
                    if seconds > 1:
                        fps = frame_counter_per_sec
                        frame_counter_per_sec = 0
                        start_time = time()
                    outstr = "Frames: {}, FPS: {}".format(frame_index, fps) 
                    sys.stdout.write('\r'+ outstr)
                    frame_counter_per_sec = frame_counter_per_sec + 1
                    frame_index = frame_index + 1
                    rawCapture.truncate(0)
                else:
                    break
        except (KeyboardInterrupt, SystemExit):
            logging.info('Exit due to keyboard interrupt')
        except Exception:
            exp = traceback.format_exc()
            logging.error(exp)
        finally:
            #streamimage.close()
            del stream
            del rawCapture
            del payload
            logging.info("Stopping the stream for device: {}.".format(device))
            logging.info("Total Published frames: {}, FPS:{}.".format(frame_index, fps))

if __name__ == "__main__":
    backend.start(device, callback=streamVideo)
