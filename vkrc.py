#!/usr/bin/env python3

"""
vkrc - A tiny, local, stateful -but definitely, definitely not real- cloud orchestration tool.
"""

import os
import argparse
import uuid
import subprocess
import logging
from pathlib import Path
from typing import List

def setup_logging() -> None:
  """Set up basic logging"""
  logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def parse_arguments() -> argparse.Namespace:
  """Parse command-line arguments"""
  parser = argparse.ArgumentParser(description="Local, stateful cloud orchestration tool")
  subparsers = parser.add_subparsers(dest="command", required=True)
  
  list_parser = subparsers.add_parser("list", help="List all VMs and their status")
  list_parser.add_argument("-a", "--all", action="store_true", help="List all VMs")

  create_parser = subparsers.add_parser("create", help="Create a new VM")
  create_parser.add_argument("-n", "--name", help="VM name")
  create_parser.add_argument("-c", "--cores", default=2, type=int, help="Number of CPU cores")
  create_parser.add_argument("-m", "--memory", default=4, type=int, help="Member in GB")
  create_parser.add_argument("-i", "--iso", nargs="?", const=None, help="ISO image for VM startup")
  create_parser.add_argument("-d", "--disk", default="", help="VM disk image")
  create_parser.add_argument("-s", "--size", default=10, type=int, help="Disk size in GB")
  create_parser.add_argument("-x", "--headless", action="store_true", help="Run headless")
  create_parser.add_argument("-t", "--terminate", action="store_true", help="Terminate VPN")
  create_parser.add_argument("-z", "--cloud", action="store_true", help="VM will use user-data initialization")
  create_parser.add_argument("-f", "--forward", action="store_true", help="Forward host ports to guest") #FIXME format?
  create_parser.add_argument("-b", "--bridged", action="store_true", help="Bridge network to host")
  create_parser.add_argument("-p", "--shared", action="store_true", help="Shared network")
  create_parser.add_argument("-dr", "--dry-run", action="store_true", help="Print (do not run) the command")

  # FIXME this alone does not run the VM, we need to duplicate the argument parsing, or load from configuration file
  # FIXME decision point: do we allow different create/run time options? E.g. 2 cores on create, 4 on run.
  start_parser = subparsers.add_parser("start", help="Start a VM") 
  start_parser.add_argument("-n", "--name", help="Name of the VM to start")

  stop_parser = subparsers.add_parser("stop", help="Stop a VM")
  stop_parser.add_argument("-n", "--name", help="Name of the VM to stop")
  stop_parser.add_argument("-t", "--terminate", help="Terminate after stop")

  terminate_parser = subparsers.add_parser("terminate", help="Terminate a VM")
  terminate_parser.add_argument("-n", "--name", help="VM name to terminate")

  return parser.parse_args()

def list_instances() -> None:
  """List all instances, regardless of state"""
  instances_dir = Path("instances")
  if instances_dir.exists():
    for instance in instances_dir.iterdir():
      status = "running" if subprocess.run(["pgrep", "-f", instance.name], capture_output=True, text=True).returncode == 0 else "stopped"
      if instance.is_dir():
        print(f"{instance.name:<30}\t| {status:<15}")
  else:
    logging.info("No instances found")

def run_command(cmd: List[str]) -> None:
  """Run a command"""
  logging.info("Running: %s", " ".join(cmd))
  try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30) #FIXME this is meant to be a long-running VM, is this going to time it out?
    if result.returncode != 0:
      logging.error("Command failed with error: %s", result.stderr)
      raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
  except subprocess.TimeoutExpired as e:
    logging.error("Command timed out: %s", cmd)
    raise

def create_instance(args: argparse.Namespace) -> Path:
  """Create a new VM"""
  instance_id = uuid.uuid4().hex # FIXME we need an instance_id regardless of whether the user passes a name or not
  name = args.name if args.name else instance_id
  vm_path = Path("instances") / name #FIXME divided by name?
  if not vm_path.exists():
    vm_path.mkdir(parents=True, exist_ok=True) #FIXME something something filesystem
    # Copy firmware files
    run_command(["cp", "./edk2/edk2-aarch64-code.fd", str(vm_path / "edk2-aarch64-code.fd")])
    run_command(["cp", "./edk2/edk2-arm-vars.fd", str(vm_path / "edk2-arm-vars.fd")])
    if not args.disk:
      disk_path = vm_path / f"{name}.img"
      args.disk = str(disk_path)
      if not os.access(vm_path, os.W_OK):
        logging.error("VM disk path is not writable: %s", vm_path)
        raise PermissionError("VM disk path is not writable")
      # Create disk image
      run_command(["qemu-img", "create", str(disk_path), f"{args.size}G", "-f", "qcow2"])
  return vm_path

def run_instance(args: argparse.Namespace, vm_path: Path) -> None:
  """Run a VM instance using QEMU"""
  # FIXME loads of configuration things that were skipped here
  # FIXME this needs to read the configuration of the VM from a file in vm_path
  qemu_cmd = [
    "qemu-system-aarch64", # FIXME what if not on arm64? Bigger problem here
    "-machine", "virt",
    "-cpu", "host",
    "-smp", str(arg.cores),
    "-m", f"{args.memory}G",
    "-drive", "if=virtio,file{args.disk},format=qcow2"
  ]

  if args.headless:
    qemu_cmd.append("-nographic")
  else:
    qemu_cmd.extend(["-device", "virtio-gpu", "-display", "default"])

  logging.info("Starting VM with command: %s", " ".join(qemu_cmd))

  if not args.dry_run:
    run_command(qemu_cmd)

def main() -> None:
  setup_logging()
  args = parse_arguments()

  if args.command == "list":
    list_instances()
  elif args.command == "create":
    vm_path = create_instance(args)
    logging.info("Created VM: %s at %s", args.name, vm_path) # FIXME if name is empty this needs to show instance_id
  elif args.command == "start":
    run_intance(args)
  elif args.command == "stop":
    stop_instance(args.name)
  elif args.command == "terminate":
    terminate_instance(args.name)

if __name__ == "__main__":
  main()


#---COMMENT_EVERYTHING_UNDER_HERE---
#if args.list == True:
#  print(list_instances())
#  exit()
#
#if args.name == "":
#  args.name = vm_instance_id
#
#vm_path = "instances/{}".format(args.name)
#if not os.path.exists(vm_path):
#  os.makedirs(vm_path)
#  os.system("cp ./edk2/edk2-aarch64-code.fd {}/".format(vm_path))
#  os.system("cp ./edk2/edk2-arm-vars.fd {}/".format(vm_path))
#  if args.disk == "":
#    args.disk = vm_path + "/" + args.name + ".img"
#    os.system("qemu-img create {} {}G -f qcow2".format(args.disk, args.size))
#  else:
#    # This bit reads a bit complicated 
#    os.system("cp {} {}/{}.img".format(args.disk, vm_path, vm_instance_id))
#    args.disk = vm_path + "/" + vm_instance_id + ".img"
#    size_add = int(args.size) - 10
#    if size_add > 0:
#      os.system("qemu-img resize -f qcow2 {} +{}G".format(args.disk, size_add))
#else:
#  args.disk = vm_path + "/" + args.name + ".img"
#
## User data if we are on a "cloud" instance
#if args.cloud == True:
#  print("User data injection selected.")
#  user_data_path = vm_path + "/" + "user-data.img"
#  user_data_file = "user-data/user-data.img"
#  os.system("cp {} {}".format(user_data_file, user_data_path))
#
#def create_mac_address():
#  mac_address = "00:11:22:33:44:55"
#  return mac_address
#
#base_command = "qemu-system-aarch64"
#flags = ("-nodefaults",
#         "-cpu host",
#         "-smp cores={}".format(args.cores),
#         "-machine virt",
#         "-accel hvf",
#         "-m {}".format(int(args.memory)*1024),
#         ["-device virtio-gpu","-nographic"][args.headless],
#         # Network
#         ["", "-device virtio-net-pci,mac={},netdev=net0".format(create_mac_address())][args.bridged or args.shared],
#         ["", "-netdev vmnet-bridged,id=net0,ifname=en0"][args.bridged],
#         ["", ""][args.shared],
#         ["","-nic user,model=virtio,hostfwd=tcp:127.0.0.1:7822-0.0.0.0:22"][args.forward],
#         # Display
#         ["-display cocoa,show-cursor=on",""][args.headless],
#         "-device qemu-xhci",
#         "-device usb-kbd",
#         "-device usb-tablet",
#         "-device intel-hda",
#         "-audiodev coreaudio,id=audio",
#         "-boot d",
#         ["", "-cdrom {}".format(args.iso)][args.iso != None],
#         "-drive if=pflash,format=raw,readonly=on,file={}/edk2-aarch64-code.fd".format(vm_path),
#         "-drive if=pflash,format=raw,file={}/edk2-arm-vars.fd".format(vm_path),
#         "-drive if=virtio,format=qcow2,file={}".format(args.disk),
#         ["","-drive file={}/user-data.img,format=raw".format(vm_path)][args.cloud]
#         )
#
#command = "{} {}".format(base_command, ' '.join([x for x in flags]))
#
#if args.dry_run == True:
#  print("Command: %s" % (command))
#else:
#  print("Command: %s" % (command))
#  os.system(command)
#
#if args.terminate == True:
#  os.system("rm -rf {}".format(vm_path))
