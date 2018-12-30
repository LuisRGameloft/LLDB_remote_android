import os
import subprocess
import os.path
import urllib
import zipfile

g_adb_tool                  = os.environ['ADB_PATH'] + '/adb.exe'
g_android_package           = os.environ['ANDROID_PACKAGE']
g_android_main_activity     = os.environ['MAIN_ACTIVITY']
g_arch_device               = os.environ['ARCH_DEVICE']
g_current_working_path      = os.getcwd()
g_LLDB_working_path         = os.path.join(g_current_working_path, 'LLDB', 'Windows')
g_android_repository_url    = 'https://dl.google.com/android/repository/'
g_lldb_tool                 = 'lldb-3.1.4508709-windows.zip'

def main():

    #Check for LLDB tool
    if not os.path.exists(os.path.join(g_LLDB_working_path, 'bin', 'LLDBFrontend.exe')):
        print "LLDB doesn't exists, Downloading Android LLDB tool ... "
        LLDB_zip_file = os.path.join(g_current_working_path, g_lldb_tool)
        urllib.urlretrieve (g_android_repository_url + g_lldb_tool, LLDB_zip_file)
        print "Downloaded!!! , Uncompressing ... "
        
        #Check for LLDB paths
        LLDB_path = os.path.join(g_current_working_path, 'LLDB')
        if not os.path.exists(LLDB_path):
            os.mkdir(LLDB_path)

        LLDB_path = os.path.join(LLDB_path, 'Windows')
        if not os.path.exists(LLDB_path):
            os.mkdir(LLDB_path)

        LLDB_zip = zipfile.ZipFile(LLDB_zip_file)
        LLDB_zip.extractall(g_LLDB_working_path)
        LLDB_zip.close()
        print "Downloaded!!! , Uncompressing ... Done"

    print "Install LLDB files into device"
    
    #Install LLDB Server
    lldb_server_name    = 'lldb-server' 
    lldb_server_path    = os.path.join(g_LLDB_working_path, 'android', g_arch_device, lldb_server_name)
    command = g_adb_tool + ' push ' + lldb_server_path + ' /data/local/tmp/' + lldb_server_name
    subprocess.Popen(command, stdout=subprocess.PIPE).wait()

    #Install LLDB Script
    lldb_server_script  = 'start_lldb_server.sh'
    lldb_server_script_path  = os.path.join(g_LLDB_working_path, 'android', lldb_server_script)
    command = g_adb_tool + ' push ' + lldb_server_script_path + ' /data/local/tmp/' + lldb_server_script
    subprocess.Popen(command, stdout=subprocess.PIPE).wait()

    #Stop Current APP session
    command = g_adb_tool + ' shell am force-stop ' + g_android_package
    subprocess.Popen(command, stdout=subprocess.PIPE).wait()

    #Start Current APP session
    command = g_adb_tool + ' shell am start -n "' + g_android_package + '/' + g_android_main_activity + '" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -D'
    subprocess.Popen(command, stdout=subprocess.PIPE).wait()

    #Create LLDB folders into device /data/data/<package-id>/lldb and ~/lldb/bin
    command = g_adb_tool + " shell run-as " + g_android_package + " sh -c 'mkdir /data/data/" + g_android_package + "/lldb; mkdir /data/data/" + g_android_package + "/lldb/bin'"
    subprocess.Popen(command, stdout=subprocess.PIPE).wait()

    #Install lldbserver into package folder /data/data/<package-id>/lldb/bin
    command = g_adb_tool + " shell \"cat /data/local/tmp/lldb-server | run-as " + g_android_package + " sh -c 'cat > /data/data/" + g_android_package + "/lldb/bin/lldb-server && chmod 700 /data/data/" + g_android_package + "/lldb/bin/lldb-server'\""
    subprocess.Popen(command, stdout=subprocess.PIPE).wait()
    
    #Install start_lldb_server.sh script into package folder /data/data/<package-id>/lldb/bin
    command = g_adb_tool + " shell \"cat /data/local/tmp/start_lldb_server.sh | run-as " + g_android_package + " sh -c 'cat > /data/data/" + g_android_package + "/lldb/bin/start_lldb_server.sh && chmod 700 /data/data/" + g_android_package + "/lldb/bin/start_lldb_server.sh'\""
    subprocess.Popen(command, stdout=subprocess.PIPE).wait()
    
    #Install start_lldb_server.sh script into package folder /data/data/<package-id>/lldb/bin
    print "Debugger is running ..."
    command = g_adb_tool + " shell run-as " + g_android_package + " sh -c '/data/data/" + g_android_package + "/lldb/bin/start_lldb_server.sh /data/data/" + g_android_package + "/lldb unix-abstract /" + g_android_package + "-0 platform-1545976949340.sock \"lldb process:gdb-remote packets\"'"
    subprocess.call(command)
    

if __name__ == "__main__":
    main()