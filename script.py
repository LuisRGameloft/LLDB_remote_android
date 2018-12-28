import os
import subprocess

g_adb_tool              = os.environ['ADB_PATH'] + '/adb.exe'
g_android_package       = os.environ['ANDROID_PACKAGE']
g_android_main_activity = os.environ['MAIN_ACTIVITY']

def main():

    command = g_adb_tool + ' shell am force-stop ' + g_android_package
    print command
    subprocess.Popen(command, stdout=subprocess.PIPE).wait()

    command = g_adb_tool + ' shell am start -n "' + g_android_package + '/' + g_android_main_activity + '" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -D'
    subprocess.Popen(command, stdout=subprocess.PIPE).wait()

    # my code here

if __name__ == "__main__":
    main()