# plugins/tools/ — Auto-discovered tool plugins for GenericAgent
#
# Each plugin file in this directory is automatically loaded at startup.
# To add a new tool, create a .py file that uses the @register_tool decorator.
#
# Example plugin (save as my_tool.py):
#
#   from tools import register_tool
#
#   @register_tool(
#       name="my_tool",
#       description="Does something useful",
#       parameters={
#           "type": "object",
#           "properties": {
#               "input": {"type": "string", "description": "The input"},
#           },
#           "required": ["input"],
#       },
#       category="custom",
#   )
#   def handle_my_tool(args: dict, response) -> dict:
#       return {"status": "success", "result": args["input"]}
