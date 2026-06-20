# encoding=utf-8
import sys
import argparse
import subprocess
from pathlib import Path


SSH_KEY_TYPES = ("id_ed25519", "id_rsa", "id_ecdsa")


def get_default_key_path() -> Path:
    ssh_dir = Path.home() / ".ssh"
    for name in SSH_KEY_TYPES:
        key = ssh_dir / name
        if key.exists():
            return key
    return ssh_dir / "id_ed25519"


def gen_ssh_key(key_path: Path, key_type: str = "ed25519") -> None:
    ssh_dir = key_path.parent
    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    result = subprocess.run(
        ["ssh-keygen", "-t", key_type,
         "-f", str(key_path), "-N", "", "-q"],
    )
    if result.returncode != 0:
        print("生成 SSH Key 失败", file=sys.stderr)
        sys.exit(1)
    print("已生成 SSH Key: %s" % key_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 SSH Key")
    parser.add_argument("-f", "--file", help="密钥文件路径（默认 ~/.ssh/id_ed25519）")
    parser.add_argument("-t", "--type", default="ed25519",
                        choices=("ed25519", "rsa", "ecdsa"),
                        help="密钥类型（默认 ed25519）")
    parser.add_argument("--force", action="store_true", help="强制重新生成")
    args = parser.parse_args()

    if args.file:
        key_path = Path(args.file).expanduser().resolve()
    else:
        key_path = get_default_key_path()

    if key_path.exists() and not args.force:
        print("SSH Key 已存在: %s" % key_path)
    else:
        if key_path.exists() and args.force:
            key_path.unlink()
            pub_path = key_path.with_suffix(key_path.suffix + ".pub")
            if pub_path.exists():
                pub_path.unlink()
        gen_ssh_key(key_path, args.type)

    pub_path = key_path.with_suffix(key_path.suffix + ".pub")
    if pub_path.exists():
        print(pub_path.read_text().strip())


if __name__ == "__main__":
    main()
