# manage_arm64.py
# In search of a better name

# We need
# 1. Execute OS commands
# 2. Collect and pass a bunch of flags
# 3. Create vm
# 4. Stop (but do not terminate) vm
# 5. Terminate vm


import os
import argparse
import uuid

vm_instance_id = ''.join(str(uuid.uuid4()).split("-"))

parser = argparse.ArgumentParser()
parser.add_argument("-n", "--name", default="", help="VM name")
parser.add_argument("-c", "--cores", default=2, help="Number of cores")
parser.add_argument("-m", "--memory", default=4, help="Memory for VM in GB")
parser.add_argument("-i", "--iso", nargs="?", const=None, help="ISO image for VM startup")
parser.add_argument("-d", "--disk", default="", help="VM disk image")
parser.add_argument("-s", "--size", default=10, help="VM disk image size")
parser.add_argument("-x", "--headless", action='store_true', help="Run a headless VM")
parser.add_argument("-t", "--terminate", action='store_true', help="Terminate VM")
parser.add_argument("-z", "--cloud", action='store_true', help="VM will use user-data initialization")
parser.add_argument("-f", "--forward", nargs="?", const=None, help="Forward ports from localhost to VM (comma-separated please!)")

args = parser.parse_args()

if args.name == "":
  args.name = vm_instance_id

vm_path = "instances/{}".format(args.name)
if not os.path.exists(vm_path):
  os.makedirs(vm_path)
  os.system("cp ./edk2/edk2-aarch64-code.fd {}/".format(vm_path))
  os.system("cp ./edk2/edk2-arm-vars.fd {}/".format(vm_path))
  if args.disk == "":
    args.disk = vm_path + "/" + args.name + ".img"
    os.system("qemu-img create {} {}G -f qcow2".format(args.disk, args.size))
  else:
    # This bit reads a bit complicated 
    os.system("cp {} {}/{}.img".format(args.disk, vm_path, vm_instance_id))
    args.disk = vm_path + "/" + vm_instance_id + ".img"
else:
  args.disk = vm_path + "/" + args.name + ".img"

# User data if we are on a "cloud" instance
if args.cloud == True:
  user_data_path = vm_path + "/" + "user-data.img"
  user_data_file = "user-data/user-data.img"
  os.system("cp {} {}".format(user_data_file, user_data_path))

base_command = "qemu-system-aarch64"
flags = ("-nodefaults",
         "-cpu host",
         "-smp cores={}".format(args.cores),
         "-machine virt",
         "-accel hvf",
         "-m {}".format(int(args.memory)*1024),
         ["-device virtio-gpu","-nographic"][args.headless],
         ["-nic user,model=virtio","-nic user,model=virtio,hostfwd=tcp:127.0.0.1:7822-0.0.0.0:22"][args.forward != None],
         ["-display cocoa,show-cursor=on",""][args.headless],
         "-device qemu-xhci",
         "-device usb-kbd",
         "-device usb-tablet",
         "-device intel-hda",
         "-audiodev coreaudio,id=audio",
         "-boot d",
         ["", "-cdrom {}".format(args.iso)][args.iso != None],
         "-drive if=pflash,format=raw,readonly=on,file={}/edk2-aarch64-code.fd".format(vm_path),
         "-drive if=pflash,format=raw,file={}/edk2-arm-vars.fd".format(vm_path),
         "-drive if=virtio,format=qcow2,file={}".format(args.disk),
         ["","-drive file={}/user-data.img,format=raw".format(vm_path)][args.cloud]
         )

command = "{} {}".format(base_command, ' '.join([x for x in flags]))

print("Command: %s" % (command))
os.system(command)

if args.terminate == True:
  os.system("rm -rf {}".format(vm_path))
