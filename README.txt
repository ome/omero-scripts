This directory contains OmeroPy scripts which use the
OmeroScripts API. All scripts ("*.py") present in the
directory will be automatically distributed with all binary
builds. Example scripts and works-in-progress are available
on other branches in the same repository.

Scripts which would like to rely on other scripts can
use:

    import omero.<sub_dir>.<script_name>

For this to work, the official script in question must
be properly importable, i.e.:

    def run():
        client = omero.scripts.client(...)

    if __name__ == "__main__":
        run()

