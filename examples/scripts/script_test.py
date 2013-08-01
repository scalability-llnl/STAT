# STAT test suite
# invoke with ${prefix}/bin/stat-script

import sys, DLFCN
sys.setdlopenflags(DLFCN.RTLD_NOW | DLFCN.RTLD_GLOBAL)
import os, time, subprocess
import traceback

from STAT import STAT_FrontEnd, intArray, STAT_LOG_NONE, STAT_LOG_FE, STAT_LOG_BE, STAT_LOG_CP, STAT_LOG_MRN, STAT_LOG_SW, STAT_LOG_SWERR, STAT_LOG_NONE, STAT_OK, STAT_APPLICATION_EXITED, STAT_VERBOSE_ERROR, STAT_VERBOSE_FULL, STAT_VERBOSE_STDOUT, STAT_TOPOLOGY_AUTO, STAT_TOPOLOGY_DEPTH, STAT_TOPOLOGY_FANOUT, STAT_TOPOLOGY_USER, STAT_PENDING_ACK, STAT_LAUNCH, STAT_ATTACH, STAT_SERIAL_ATTACH, STAT_SAMPLE_FUNCTION_ONLY, STAT_SAMPLE_LINE, STAT_SAMPLE_PC, STAT_SAMPLE_COUNT_REP, STAT_SAMPLE_THREADS, STAT_SAMPLE_CLEAR_ON_SAMPLE, STAT_SAMPLE_PYTHON
from STAT import attach, launch, serial_attach, sample, detach, pause, resume, get_stat_fe, STATerror
from STAThelper import ProcTab, get_ProcTab

class STATapp:
    def __init__(self, launcher, exe, launcher_args = [], exe_args = []):
        self.launcher = launcher
        self.exe = exe
        self.launcher_args = launcher_args
        self.exe_args = exe_args

    def launch(self):
        launch_args = [self.launcher] + self.launcher_args + [self.exe] + self.exe_args
        try:
            launch(launch_args)
            self.stat_fe = get_stat_fe()
            self.pid = self.stat_fe.getLauncherPid()
            out_dir = self.stat_fe.getOutDir()
            file_prefix = self.stat_fe.getFilePrefix()
            self.proctab_file_path = out_dir + '/' + file_prefix + '.ptab'
            sample()
            detach()
        except Exception as e:
            sys.stderr.write('launch %s failed: %s\n' %(repr(launch_args), e))
            self.terminate()
            return False
        return True

    def terminate(self):
        if hasattr(self, 'pid'):
            subprocess.call(['kill', '-TERM', str(self.pid)])
        return True


class STATtest:
    def __init__(self, name, app, attach_options = (), sample_options_list = [{}], sleep_time = 3):
        self.name = name
        self.app = app
        self.attach_options = attach_options
        self.sample_options_list = sample_options_list
        self.sleep_time = sleep_time

    def run(self):
        attached = False
        try:
            attach_args, attach_kw_args, attach_function = self.attach_options
            sys.stdout.write('%s test beginning...\n' %(self.name))
            time.sleep(self.sleep_time)
            pid_arg = str(self.app.pid)
            if (attach_function == serial_attach):
                proctab = get_ProcTab(self.app.proctab_file_path)
                pid_list = []
                for rank, host, serial_pid, exe_index in proctab.process_list:
                    if rank % 3 == 0:
                        pid_list.append('%s@%s:%d' %(proctab.executable_paths[exe_index], host, serial_pid))
                pid_arg = pid_list
            attach_args = (pid_arg,) + attach_args
            apply(attach_function, attach_args, attach_kw_args)
            attached = True
            resume()
            for kw_args in self.sample_options_list:
                ret = apply(sample, (), kw_args)
            detach()
        except Exception as e:
            sys.stderr.write('%s test failed: %s\n' %(self.name, repr(e)))
            traceback.print_exc()
            if attached == True:
                detach()
            return False
        sys.stdout.write('%s test complete\n' %(self.name))
        return True

def run_tests(test_suites, launcher, launcher_args):
    failed_list = []
    count = 0
    for exe, tests in test_suites:
        if os.path.exists(exe) != True:
            msg = 'exe %s does not exist\n' %exe
            sys.stderr.write(msg)
            failed_list.append(msg)
            continue
    
        test_name = 'launch and sample %s' %(os.path.basename(exe))
        sys.stdout.write('\n%s test beginning...\n' %(test_name))
        app = STATapp(launcher, exe, launcher_args = num_tasks_args)
        ret = app.launch() 
        if ret == False:
            failed_list.append(test_name)
            continue
        sys.stdout.write('%s test complete\n' %(test_name))
    
        test_name = 'basic samples %s' %(os.path.basename(exe))
        sample_options = [{}, {"sample_type":STAT_SAMPLE_FUNCTION_ONLY + STAT_SAMPLE_THREADS}, {"num_traces":10}, {"sample_type":STAT_SAMPLE_FUNCTION_ONLY + STAT_SAMPLE_COUNT_REP}, {"sample_type":STAT_SAMPLE_FUNCTION_ONLY + STAT_SAMPLE_LINE}]
        attach_options = ((app.pid,), {}, attach)
        tests.insert(0, (test_name, attach_options, sample_options))
        
        for test in tests:
            count += 1
            test_name, attach_options, sample_options = test
            test = STATtest(test_name, app, attach_options = attach_options, sample_options_list = sample_options)
            ret = test.run()
            if ret == False:
                failed_list.append(test_name)
                continue
    
        sys.stdout.write("\n%s tests complete, terminating application\n\n" %os.path.basename(exe))
        app.terminate()
        time.sleep(3)
    
    if len(failed_list) != 0:
        sys.stdout.write('\n%d of %d tests failed:\n' %(len(failed_list), count))
        for failure in failed_list:
            sys.stdout.write('\t%s\n' %failure)
    else:
        sys.stdout.write('\nAll %d tests passed!\n\n' %(count))
    
    sys.exit(0)

if __name__ == "__main__":

    os.environ['STAT_USAGE_LOG'] = '/dev/null'
    os.environ['STAT_CHECK_NODE_ACCESS'] = '1'
    os.environ['STAT_CONNECT_TIMEOUT'] = '30'
    launcher = 'srun'
    num_tasks = 16
    num_tasks_args = ['-n', str(num_tasks)]
    temp_fe = STAT_FrontEnd()
    version = intArray(3)
    install_prefix = temp_fe.getInstallPrefix()
    temp_fe.getVersion(version)
    sys.stdout.write("STAT version %d.%d.%d installed in %s\n" %(version[0], version[1], version[2], install_prefix))
    
    test_suites = []
    exe = '%s/share/STAT/examples/bin/hw' %(temp_fe.getInstallPrefix())
    tests = []
    test_suites.append((exe, tests))
    
    exe = '%s/share/STAT/examples/bin/rank_test' %(temp_fe.getInstallPrefix())
    tests = []
    test_suites.append((exe, tests))
    
    exe = '%s/share/STAT/examples/bin/mpi_ringtopo' %(temp_fe.getInstallPrefix())
    tests = []
    
    test_name = 'serial attach %s' %(os.path.basename(exe))
    attach_options = ((), {}, serial_attach)
    sample_options = [{}]
    tests.append((test_name, attach_options, sample_options))
    
    test_name = 'various samples %s' %(os.path.basename(exe))
    attach_options = ((), {}, attach)
    sample_options = [{}, {"sample_type":STAT_SAMPLE_FUNCTION_ONLY + STAT_SAMPLE_THREADS}, {"num_traces":10}, {"sample_type":STAT_SAMPLE_CLEAR_ON_SAMPLE, "num_traces":10}, {"sample_type":STAT_SAMPLE_FUNCTION_ONLY + STAT_SAMPLE_COUNT_REP}, {"sample_type":STAT_SAMPLE_FUNCTION_ONLY + STAT_SAMPLE_LINE}]
    tests.append((test_name, attach_options, sample_options))
    
    test_name = "depth topology %s" %(os.path.basename(exe))
    attach_options = ((), {"topology_type":STAT_TOPOLOGY_DEPTH, "topology":"2"}, attach)
    sample_options = [{}]
    tests.append((test_name, attach_options, sample_options))
    
    test_name = "user topology %s" %(os.path.basename(exe))
    attach_options = ((), {"topology_type":STAT_TOPOLOGY_USER, "topology":"1-1"}, attach)
    sample_options = [{}]
    tests.append((test_name, attach_options, sample_options))
    
    test_name = "insufficient nodes %s" %(os.path.basename(exe))
    attach_options = ((), {"topology_type":STAT_TOPOLOGY_USER, "topology":"1-1", "share_app_nodes":False}, attach)
    sample_options = [{}]
    tests.append((test_name, attach_options, sample_options))
    
    test_name = "localhost topology %s" %(os.path.basename(exe))
    attach_options = ((), {"topology_type":STAT_TOPOLOGY_USER, "topology":"1", "share_app_nodes":False, "node_list":"localhost", "logging_tuple":(STAT_LOG_FE | STAT_LOG_BE | STAT_LOG_CP | STAT_LOG_MRN, '/g/g0/lee218/logs')}, attach)
    sample_options = [{}]
    tests.append((test_name, attach_options, sample_options))
    
    test_suites.append((exe, tests))

    run_tests(test_suites, launcher, num_tasks_args)
