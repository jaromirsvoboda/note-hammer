import subprocess
import sys

def check_android_device():
    print("Android Device Connection Check")
    print("=" * 30)
    
    # Check ADB installation
    try:
        version = subprocess.run(['adb', 'version'], 
                               capture_output=True, 
                               text=True, 
                               check=True)
        print("\n✓ ADB is installed:")
        print(version.stdout.strip())
    except FileNotFoundError:
        print("\n✗ ADB not found in PATH!")
        print("Please install Android Platform Tools and add to PATH")
        return False
    
    # Check for connected devices
    print("\nChecking for connected devices...")
    try:
        devices = subprocess.run(['adb', 'devices'], 
                               capture_output=True, 
                               text=True, 
                               check=True)
        
        print("\nDevice List:")
        print(devices.stdout)
        
        # Parse device list
        lines = devices.stdout.strip().split('\n')[1:]
        device_count = len([line for line in lines if '\tdevice' in line])
        
        if device_count > 0:
            print(f"\n✓ Found {device_count} connected device(s)")
            return True
        else:
            print("\n✗ No devices found!")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error checking devices: {e}")
        return False

def main():
    print("Checking Android device connection...")
    if not check_android_device():
        print("""
Please ensure:
1. USB debugging is enabled on your device
2. Device is connected via USB
3. You have accepted the USB debugging prompt on your device
""")
        sys.exit(1)
    else:
        print("\nDevice check passed! You can now run the main script.")

if __name__ == "__main__":
    main()