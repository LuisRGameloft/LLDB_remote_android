import os
import subprocess
import os.path
import urllib
import zipfile
import time
import signal
import sys
import multiprocessing
import tempfile
import re
import posixpath

def find_program(program, path, withext=True):
    exts = [""]
    if sys.platform.startswith("win"):
        exts += [".exe", ".bat", ".cmd"]
    
    for x in os.walk(path):
        if os.path.isdir(x[0]):
            if withext:
                for ext in exts:
                    full = x[0] + os.sep + program + ext
                    if os.path.isfile(full):
                        return full
            else:
                full = x[0] + os.sep + program
                if os.path.isfile(full):
                    return full

    print ("Cannot find Program : " + program + " in path = " + path)
    exit()

def find_path(root_path, path):
    for x in os.walk(root_path):
        if os.path.isdir(x[0]):
            found_path = os.path.join(x[0], path)
            if os.path.isdir(found_path):
                return found_path 
            
    print ("Cannot find Path : " + path )
    exit()

def find_file(file, path):
    for x in os.walk(path):
        if os.path.isdir(x[0]):
            full = x[0] + os.sep + file
            if os.path.isfile(full):
                return full
            
    print ("Cannot find file : " + file + " in path = " + path)
    exit()

def run_command(command):
    p = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    exit_code = p.returncode
    if exit_code != 0:
        print ("=== Error ===\n") 
        print ("Command : " + command) 
        print ("Output : " + stdout) 
        print ("Output Err : " + stderr) 
        print ("if this error persist, please reboot device")
        exit()

    return stdout, stderr

def get_pid_task(task, adb_tool):
    command = adb_tool + " shell ps"
    stdout, stderr = run_command(command)

    lines = re.split(r'[\r\n]+', stdout.replace("\r", "").rstrip())
    columns = lines.pop(0).split()
    
    try:
        pid_column = columns.index("PID")
    except ValueError:
        pid_column = 1

    processes = dict()
    while lines:
        columns = lines.pop().split()
        process_name = columns[-1]
        pid = columns[pid_column]
        if process_name in processes:
            processes[process_name].append(pid)
        else:
            processes[process_name] = [pid]
    
    return processes.get(task, [])

def destroy_previous_session_debugger(task, adbtool, package):
    command = adbtool + " shell ps"
    stdout, stderr = run_command(command)

    lines = re.split(r'[\r\n]+', stdout.replace("\r", "").rstrip())
    columns = lines.pop(0).split()
    
    try:
        pid_column = columns.index("PID")
    except ValueError:
        pid_column = 1

    processes = dict()
    PIDS = []
    while lines:
        columns = lines.pop().split()
        process_name = columns[-1]
        pid = columns[pid_column]

        if task in process_name:
            PIDS.append(pid)

    if PIDS:
        print ("Destroying previous LLDB server sessions")
        for pid in PIDS:
            print ("Killing processes: " + pid)
            command = adbtool + " shell run-as " + package + " kill -9 " + pid
            stdout, stderr = run_command(command)

def start_jdb(adb_tool, jdb_tool, pid):
    # Do setup stuff to keep ^C in the parent from killing us.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    # Wait until gdbserver has interrupted the program.
    time.sleep(0.5)

    command = adb_tool + " -d forward tcp:65534 jdwp:" + pid
    stdout, stderr = run_command(command)

    jdb_cmd = jdb_tool + " -connect com.sun.jdi.SocketAttach:hostname=localhost,port=65534"
    flags = subprocess.CREATE_NEW_PROCESS_GROUP
    jdb = subprocess.Popen(jdb_cmd,
                           stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,
                           creationflags=flags)

    # Wait until jdb can communicate with the app. Once it can, the app will
    # start polling for a Java debugger (e.g. every 200ms). We need to wait
    # a while longer then so that the app notices jdb.
    jdb_magic = "__has_started__"
    text_signal = 'print "{}"\n'.format(jdb_magic)
    if sys.version_info[0] == 3:
        text_signal = bytes(text_signal, 'utf-8')

    jdb.stdin.write(text_signal)
    saw_magic_str = False
    while True:
        line = jdb.stdout.readline()
        if sys.version_info[0] == 3:
            line = line.decode("utf-8")

        if line == "":
            break
        #print "jdb output: " + line.rstrip()
        if jdb_magic in line and not saw_magic_str:
            saw_magic_str = True
            time.sleep(0.3)
            exit_signal = "exit\n"
            if sys.version_info[0] == 3:
                exit_signal = bytes(exit_signal, 'utf-8')

            jdb.stdin.write(exit_signal)
    jdb.wait()
    return 0

def main():
    if sys.argv[1:2] == ["--wakeup"]:
        return start_jdb(*sys.argv[2:])

    print ("Finding adb tool ...")
    g_adb_tool                  = find_program("adb", os.path.join(os.environ['ADB_PATH'], 'platform-tools'))
    print ("Finding jdb tool ...")
    g_jdb_tool                  = find_program("jdb", os.environ['JAVA_SDK_PATH'])
    print ("Finding gdb tool ...")
    g_lldb_path                 = os.environ['LLDB_PATH']
    g_lldb_tool                 = find_program("lldb", g_lldb_path)
    g_android_package           = os.environ['ANDROID_PACKAGE_ID']
    g_android_main_activity     = os.environ['MAIN_ACTIVITY']
    g_current_working_path      = os.getcwd()
    g_current_miliseconds       = str(int(round(time.time() * 1000)))
    
    #Check if device is connected
    command = g_adb_tool + " devices"
    stdout, stderr = run_command(command)

    lines = re.split(r'[\r\n]+', stdout.replace("\r", "").rstrip())
    if len(lines) < 2:
        print ("Error: device disconnected!")
        exit()
    
    if not "device" in lines[1]:
        print ("Error: device disconnected!")
        exit()

    #Detect if App is debuggeable
    command = g_adb_tool + " shell run-as " + g_android_package + " echo yes"
    p = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if ("is not debuggable" in stderr) or ("is not debuggable" in stdout):
        print ("Your APK is not debuggable")
        exit()

    #Detect ABI's device
    #Stop Current APP session
    command = g_adb_tool + ' shell getprop ro.product.cpu.abi '
    stdout, stderr = run_command(command)

    #detect ABI
    detectABI = stdout
    g_detected_abi = detectABI.lower().strip()
    
    #destroy previous debugger session
    destroy_previous_session_debugger("lldb-server", g_adb_tool, g_android_package)
    
    print ("Install LLDB files into device")
    
    #Install LLDB Server
    lldb_server_path = find_path(g_lldb_path, g_detected_abi)
    lldb_server_name    = 'lldb-server' 
    lldb_server_path_tool = os.path.join(lldb_server_path, lldb_server_name)
    command = g_adb_tool + ' push ' + lldb_server_path_tool + ' /data/local/tmp/' + lldb_server_name
    stdout, stderr = run_command(command)
    
    #Install LLDB Script
    lldb_server_script  = 'start_lldb_server.sh'
    lldb_server_script_path = find_file(lldb_server_script, g_lldb_path)
    command = g_adb_tool + ' push ' + lldb_server_script_path + ' /data/local/tmp/' + lldb_server_script
    stdout, stderr = run_command(command)

    #Stop Current APP session
    command = g_adb_tool + ' shell am force-stop ' + g_android_package
    stdout, stderr = run_command(command)
    
    #Start Current APP session
    command = g_adb_tool + ' shell am start -n "' + g_android_package + '/' + g_android_main_activity + '" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -D'
    stdout, stderr = run_command(command)
    
    #Wait for one second
    time.sleep(1)

    # Get Current PID for current debugger session
    pids = get_pid_task(g_android_package, g_adb_tool)
    if len(pids) == 0:
        error("Failed to find running process '{}'".format(g_android_package))
    if len(pids) > 1:
        error("Multiple running processes named '{}'".format(g_android_package))
    
    current_pid = pids[0]

    #check if exist folder /data/data/<package-id>/lldb 
    command = g_adb_tool + " shell run-as " + g_android_package + " sh -c 'if [ -d \"/data/data/" + g_android_package + "/lldb\" ]; then echo \"1\"; else echo \"0\"; fi;'"
    stdout, stderr = run_command(command)
    if stdout.strip() == '0':
        #Create LLDB folders into device /data/data/<package-id>/lldb 
        command = g_adb_tool + " shell run-as " + g_android_package + " sh -c 'mkdir /data/data/" + g_android_package + "/lldb'"
        stdout, stderr = run_command(command)

    #check if exist folder /data/data/<package-id>/lldb/bin
    command = g_adb_tool + " shell run-as " + g_android_package + " sh -c 'if [ -d \"/data/data/" + g_android_package + "/lldb/bin\" ]; then echo \"1\"; else echo \"0\"; fi;'"
    stdout, stderr = run_command(command)
    if stdout.strip() == '0':
        #Create LLDB folders into device /data/data/<package-id>/lldb/bin
        command = g_adb_tool + " shell run-as " + g_android_package + " sh -c 'mkdir /data/data/" + g_android_package + "/lldb/bin'"
        stdout, stderr = run_command(command)

    #Install lldb-server into package folder /data/data/<package-id>/lldb/bin
    command = g_adb_tool + " shell \"cat /data/local/tmp/" + lldb_server_name + " | run-as " + g_android_package + " sh -c 'cat > /data/data/" + g_android_package + "/lldb/bin/" + lldb_server_name + " && chmod 700 /data/data/" + g_android_package + "/lldb/bin/" + lldb_server_name + "'\""
    stdout, stderr = run_command(command)
    
    #Install start_lldb_server.sh into package folder /data/data/<package-id>/lldb/bin
    command = g_adb_tool + " shell \"cat /data/local/tmp/" + lldb_server_script + " | run-as " + g_android_package + " sh -c 'cat > /data/data/" + g_android_package + "/lldb/bin/" + lldb_server_script + " && chmod 700 /data/data/" + g_android_package + "/lldb/bin/" + lldb_server_script + "'\""
    stdout, stderr = run_command(command)

    #start gbserver into package folder /data/data/<package-id>/gdb/bin
    print ("Debugger is running ...")
    command = g_adb_tool + " shell run-as " + g_android_package + " sh -c '/data/data/" + g_android_package + "/lldb/bin/" + lldb_server_script + " /data/data/" + g_android_package + "/lldb unix-abstract /" + g_android_package + "-0 platform-" + g_current_miliseconds + ".sock \"lldb process:gdb-remote packets\"'"
    debugger_process = subprocess.Popen(command, stdout=subprocess.PIPE)

   # Get Current Device's name connected
    command = g_adb_tool + " devices"
    stdout, stderr = run_command(command)
    device_name = stdout.split("\n")[1]
    device_name = device_name.split()[0]
    device_name = device_name.strip()

    #Create script_commands for LLDB
    command_working_lldb = "platform select remote-android\n"
    command_working_lldb += "platform connect unix-abstract-connect://" + device_name + "/" + g_android_package + "-0/platform-" + g_current_miliseconds + ".sock\n"
    command_working_lldb += "process attach -p " + current_pid + "\n"
    command_working_lldb += "script import subprocess\n"
    command_working_lldb += "script subprocess.Popen({})\n".format(repr(
            [
                "python",
                os.path.realpath(__file__),
                "--wakeup",
                g_adb_tool,
                g_jdb_tool,
                current_pid,
            ]))

    #Create Tmp file
    lldb_script_fd, lldb_script_path = tempfile.mkstemp()
    os.write(lldb_script_fd, command_working_lldb)
    os.close(lldb_script_fd)

    #Attach to LLDB
    lldb_process = subprocess.Popen(g_lldb_tool + " -s " + lldb_script_path, creationflags=subprocess.CREATE_NEW_CONSOLE)
    while lldb_process.returncode is None:
        try:
            lldb_process.communicate()
        except KeyboardInterrupt:
            pass
        
    os.unlink(lldb_script_path)

if __name__ == "__main__":
    main()
