
import os
import sys


class InstallType:
    docker = "docker"
    native = "native"

def detect_install_type():
    ret = os.system("type docker")
    if ret == 0:
        return InstallType.docker
    return InstallType.native

def install_mysql(install_type=""):
    if install_type == "":
        install_type = detect_install_type()

    if install_type == InstallType.docker:
        install_by_docker()
    elif install_type == InstallType.native:
        install_by_native()
    else:
        print(f"unknown install_type: {install_type}")
        sys.exit(1)


def install_by_docker():
    os.system("sudo docker pull mysql:5.7")

def install_by_native():
    # TODO 不同环境的版本
    pass

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        if __doc__ is not None:
            print(__doc__.strip())
        else:
            print("Usage: " + sys.argv[0] + " [options]")
        sys.exit(0)

    install_mysql(install_type="")