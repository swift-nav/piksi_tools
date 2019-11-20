import os, sys, subprocess, time, pytest, threading

@pytest.mark.slow
@pytest.mark.parametrize("filename",
    ["./tests/data/piksi.bin", "./tests/data/20170513-180207.1.1.26.bin"])
def test_console_smoke(filename):
    """
    Console smoketest.

    Tests that piksi console can be started and keeps running for 10 s, after
    which it is killed. This test requires a graphical environment.
    """
    display = os.environ['DISPLAY']
    home = os.environ['HOME']
    path = os.environ['PATH']
    envs = {'PYTHONPATH': '.',
            'DISPLAY': display,
            'HOME': home,
            'PATH': path,
            'QT_DEBUG_PLUGINS': '1',
           }
    if 'VIRTUAL_ENV' in os.environ.keys():
        envs['VIRTUAL_ENV'] = os.environ['VIRTUAL_ENV']
    console_proc = subprocess.Popen([sys.executable, "-u",
                                     "piksi_tools/console/console.py",
                                     "--file", "--error", "-p", filename],
                                    env=envs,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
    timeout = 10
    t0 = time.time()
    killer_timer = threading.Timer(timeout, lambda proc: proc.kill(), args=[console_proc])
    killer_timer.start()
    assert console_proc.poll() is None, "piksi console should have started"

    output,_ = console_proc.communicate()
    running_time = round(time.time() - t0, 1)
    killer_timer.cancel() # no effect if the timer was already executed
    if len(output) > 0:
        print("console.py output:")
        print(output.decode('ascii'))

    assert running_time >= timeout, "piksi console terminated unexpectedly soon"
    assert console_proc.returncode < 0, "piksi console was not externally killed"
