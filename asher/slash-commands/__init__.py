"""Slash-command handlers — future interactive commands like /account, /logout."""
# This package is loaded dynamically (importlib.import_module) because the
# directory name contains a hyphen and is not a valid Python identifier.
# Each slash command will be registered via a discovery mechanism here.
