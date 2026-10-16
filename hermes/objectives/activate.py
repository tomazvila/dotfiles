"""Activate only the tested Hermes runtime; preserve unrelated dotfiles changes."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import sqlite3
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("package", type=Path)
parser.add_argument("backup", type=Path)
args = parser.parse_args()
package = args.package.resolve()
home = Path.home()
hermes_home = home / ".hermes"
backup = args.backup.resolve()
launch_agents = home / "Library/LaunchAgents"
labels = ["ai.hermes.gateway", "ai.hermes.dashboard"]
runtime = hermes_home / "objective-runtime"
links = {runtime: package, home / ".local/bin/hermes": package / "bin/hermes", home / ".local/bin/hermes-objectives": package / "bin/hermes-objectives"}
require = lambda condition, message: None if condition else (_ for _ in ()).throw(RuntimeError(message))
require(not backup.exists(), "use a new backup directory")
for link in links:
    require(not link.exists() or link.is_symlink(), f"refusing to replace non-symlink: {link}")
subprocess.run([str(package / "bin/python"), "-c", "from hermes_cli import kanban_db,kanban_objectives; assert 'hermes-objective-runtime' in kanban_db.__file__; print(kanban_db.__file__)"], check=True)
db = hermes_home / "kanban.db"
with sqlite3.connect(db) as conn:
    running = conn.execute("SELECT id FROM tasks WHERE status='running'").fetchall()
require(not running, f"drain existing workers before activation: {running}")
backup.mkdir(parents=True, mode=0o700)
manifest = {"package": str(package), "links": {str(p): os.readlink(p) if p.is_symlink() else None for p in links}}
(backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
with sqlite3.connect(db) as conn, sqlite3.connect(backup / "kanban-before.db") as snapshot:
    conn.backup(snapshot)
plists = {}
for label in labels:
    path = launch_agents / (label + ".plist")
    shutil.copy2(path, backup / path.name)
    plists[label] = plistlib.loads(path.read_bytes())
domain = f"gui/{os.getuid()}"
stopped = []
try:
    for label in labels:
        subprocess.run(["launchctl", "bootout", domain, str(launch_agents / (label + ".plist"))], check=True)
        stopped.append(label)
    for link, target in links.items():
        link.parent.mkdir(parents=True, exist_ok=True)
        temporary = link.with_name(link.name + ".objectives-next")
        require(not temporary.exists() and not temporary.is_symlink(), f"activation temporary link exists: {temporary}")
        temporary.symlink_to(target)
        temporary.replace(link)
    for label, settings in plists.items():
        argv = settings["ProgramArguments"]
        if label == "ai.hermes.gateway":
            for index, value in enumerate(argv):
                if value.startswith("/nix/store/") and Path(value).name.startswith("python"):
                    argv[index] = str(runtime / "bin/python")
        else:
            argv[0] = str(runtime / "bin/hermes")
        env = settings.setdefault("EnvironmentVariables", {})
        env["PATH"] = str(runtime / "bin") + ":" + env.get("PATH", "/usr/bin:/bin")
        env["HERMES_BIN"] = str(runtime / "bin/hermes")
        (launch_agents / (label + ".plist")).write_bytes(plistlib.dumps(settings))
    for label in labels:
        subprocess.run(["launchctl", "bootstrap", domain, str(launch_agents / (label + ".plist"))], check=True)
    print(json.dumps({"activated": str(package), "backup": str(backup)}))
except Exception:
    # Restore only runtime links/services. Never replace the live task DB.
    for label in labels:
        subprocess.run(["launchctl", "bootout", domain, str(launch_agents / (label + ".plist"))], check=False, capture_output=True)
        shutil.copy2(backup / (label + ".plist"), launch_agents / (label + ".plist"))
    for link in links:
        prior = manifest["links"][str(link)]
        if link.is_symlink():
            link.unlink()
        if prior is not None:
            link.symlink_to(prior)
    for label in stopped:
        subprocess.run(["launchctl", "bootstrap", domain, str(launch_agents / (label + ".plist"))], check=False)
    raise
