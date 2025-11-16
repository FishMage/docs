import argparse
import os
import subprocess
import sys

import yaml

# --- Custom YAML handling to preserve tags ---


class EnvTag:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"EnvTag({self.value})"


class PythonNameTag:
    def __init__(self, suffix):
        self.suffix = suffix

    def __repr__(self):
        return f"PythonNameTag({self.suffix})"


def env_constructor(loader, node):
    if isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_scalar(node)
    return EnvTag(value)


def env_representer(dumper, data):
    if isinstance(data.value, list):
        return dumper.represent_sequence("!ENV", data.value)
    return dumper.represent_scalar("!ENV", str(data.value))


def python_name_multi_constructor(loader, tag_suffix, node):
    return PythonNameTag(tag_suffix)


def python_name_representer(dumper, data):
    return dumper.represent_scalar(f"tag:yaml.org,2002:python/name:{data.suffix}", "")


# Register with SafeLoader
yaml.SafeLoader.add_constructor("!ENV", env_constructor)
yaml.SafeLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/name:", python_name_multi_constructor
)


# Custom Dumper
class CustomDumper(yaml.SafeDumper):
    pass


CustomDumper.add_representer(EnvTag, env_representer)
CustomDumper.add_representer(PythonNameTag, python_name_representer)

# --- End Custom YAML handling ---


def main():
    parser = argparse.ArgumentParser(description="Serve a subset of the documentation.")
    parser.add_argument(
        "section",
        help="The section of the nav to include (e.g., 'LangGraph', 'Integrations'). Case-insensitive.",
    )
    parser.add_argument(
        "--config", default="mkdocs.yml", help="Path to the input mkdocs.yml file."
    )
    parser.add_argument(
        "--out",
        default="mkdocs.subset.yml",
        help="Path to the output temporary config file.",
    )
    parser.add_argument(
        "--clean", action="store_true", help="Build a clean version (no dirty reload)."
    )

    args = parser.parse_args()

    try:
        with open(args.config) as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        print(f"Error: Could not find {args.config}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}")
        sys.exit(1)

    if "nav" not in config:
        print("Error: 'nav' section not found in mkdocs.yml")
        sys.exit(1)

    original_nav = config["nav"]
    new_nav = []

    target = args.section.lower()
    found = False

    for item in original_nav:
        # Item is usually a dict { "Name": "path" } or { "Name": [...] }
        if isinstance(item, dict):
            key = list(item.keys())[0]
            value = item[key]

            # Always keep "Get started" or root index to ensure site builds
            if "get started" in key.lower() or (
                isinstance(value, str) and value == "index.md"
            ):
                new_nav.append(item)
                continue

            # Check if this is the requested section
            if target in key.lower():
                new_nav.append(item)
                found = True
        elif isinstance(item, str):
            # String item
            if target in item.lower():
                new_nav.append(item)
                found = True

    if not found:
        print(f"Error: No section matching '{args.section}' found in nav.")
        print("Available top-level sections:")
        for item in original_nav:
            if isinstance(item, dict):
                print(f" - {list(item.keys())[0]}")
            else:
                print(f" - {item}")
        sys.exit(1)

    config["nav"] = new_nav

    # Write the new config
    with open(args.out, "w") as f:
        yaml.dump(config, f, Dumper=CustomDumper, sort_keys=False)

    print(
        f"Generated {args.out} with sections: {[list(i.keys())[0] for i in new_nav if isinstance(i, dict)]}"
    )

    # Run mkdocs serve
    cmd = ["uv", "run", "--no-sync", "python", "-m", "mkdocs", "serve", "-f", args.out]
    if not args.clean:
        cmd.append("--dirty")

    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        if os.path.exists(args.out):
            os.remove(args.out)
            print(f"Removed {args.out}")


if __name__ == "__main__":
    main()
