"""File management tools (sandboxed to DATASTORE_DIR)."""

from os import getenv

from langchain_community.agent_toolkits import FileManagementToolkit

working_directory = getenv("DATASTORE_DIR")
toolkit = FileManagementToolkit(root_dir=working_directory)
file_management_tools = toolkit.get_tools()
