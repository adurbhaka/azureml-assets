# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
from git import Repo
from pathlib import Path
from typing import Dict

import azureml.assets as assets
import azureml.assets.util as util
from azureml.assets.util import logger


def create_template_data(asset_config: assets.AssetConfig, release_directory_root: Path = None, version: str = None,
                         include_commit_hash: bool = False) -> Dict[str, object]:
    # Start with common items
    data = {
        'asset': {
            'name': asset_config.name,
            'version': version or asset_config.version,
        }
    }

    # Handle repo
    if release_directory_root:
        # Determine build context path in repo
        asset_release_subdir = util.get_asset_release_dir(asset_config, release_directory_root)
        asset_release_dir = asset_release_subdir.relative_to(release_directory_root)

        # Add to data
        repo = Repo(release_directory_root)
        remote_url = repo.remotes.origin.url
        if not remote_url.endswith(".git"):
            remote_url = remote_url.rstrip("/") + ".git"
        data['asset']['repo'] = {
            'url': remote_url
        }
        if include_commit_hash:
            data['asset']['repo']['commit_hash'] = repo.head.commit.hexsha

    # Augment with type-specific data
    if asset_config.type == assets.AssetType.ENVIRONMENT:
        environment_config = asset_config.environment_config_as_object()
        data['image'] = {'name': environment_config.image_name}
        if environment_config.build_enabled:
            data['image']['dockerfile'] = {
                'path': environment_config.dockerfile
            }
            publish_location_hostname = environment_config.publish_location_hostname
            if publish_location_hostname:
                data['image']['publish'] = {
                    'hostname': publish_location_hostname
                }
            if release_directory_root:
                data['asset']['repo']['build_context'] = {
                    'path': Path(asset_release_dir, environment_config.context_dir).as_posix()
                }

    return data


def update(asset_config: assets.AssetConfig, release_directory_root: Path = None, output_file: Path = None,
           version: str = None, include_commit_hash: bool = False, data: Dict[str, object] = None):
    """Update template tags in an asset's spec file using data from the asset config and any extra configs.

    Args:
        asset_config (assets.AssetConfig): AssetConfig object.
        release_directory_root (Path, optional): Directory to which the release branch has been cloned.
        output_file (Path, optional): File to which updated spec file will be written.
                                      If unspecified, the original spec file will be updated.
        version (str, optional): Version to use instead of the one in the asset config file.
        include_commit_hash (bool, optional): Whether to include the commit hash in the data available for
                                              template replacemnt.
        data (Dict[str, object], optional): If provided, use this data instead of calling create_template_data().
    """
    # Reuse or create data
    data = data or create_template_data(asset_config=asset_config, release_directory_root=release_directory_root,
                                        version=version, include_commit_hash=include_commit_hash)

    # Load spec template and render
    with open(asset_config.spec_with_path) as f:
        contents = util.render(f.read(), data)

    # Write spec
    if output_file == "-":
        logger.print(contents)
    else:
        if output_file is None:
            output_file = asset_config.spec_with_path
        with open(output_file, "w") as f:
            f.write(contents)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--asset-config", required=True, type=Path,
                        help="Asset config file that points to the spec file to update")
    parser.add_argument("-r", "--release-directory", type=Path,
                        help="Directory to which the release branch has been cloned")
    parser.add_argument("-o", "--output", type=Path,
                        help="File to which output will be written. Defaults to the original spec file.")
    args = parser.parse_args()

    update(asset_config=args.asset_config, release_directory_root=args.release_directory, output_file=args.output)
