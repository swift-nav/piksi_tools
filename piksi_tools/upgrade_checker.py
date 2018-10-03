import subprocess
import time 

callargs = ["python", "-m", "bootload_v3", "-p", "/dev/cu.usbserial"
            ,"/Users/jwilson/SwiftNav/FW/PiksiMulti-v2.1.8.bin", "-b", "115200"]

successcount = 0
failcount = 0
cookies = True 
test_start_t = time.time()
while cookies == True:
    cycle_start_t = time.time()
    try:
        st = time.time()
        x = subprocess.check_call(callargs)
        successcount += 1
        cycle_t = time.time() - cycle_start_t
        elapsed_t = time.time() - test_start_t,
        print("FW UPGRADE SUCCESS - 115200 success count: {}, upgrade time: {}  elapsed time: {} ".format(successcount, cycle_t, elapsed_t))

    except subprocess.CalledProcessError as e:
        print(e)
        failcount += 1
        elapsed_t = time.time() - start_t
        cycle_t = time.time() - cycle_start_t
        print("FAIL FAIL FAIL - 115200 - # : {}, elapsed_t: {}".format(failcount,cycle_t, elapsed_t))

    finally:
        print('sleep 60 seconds')
        time.sleep(60)
