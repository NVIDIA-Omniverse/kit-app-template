# loads a USD file and plays its timeline after load.
import argparse
import omni.usd
import omni.kit
import omni.kit.commands
import json
import carb
import asyncio
import innoactive.serverextension

parser = argparse.ArgumentParser()
parser.add_argument("--path", help="Path to USD stage.")

options = parser.parse_args()

async def startup_script():

    emptyStage = "usd/Empty/Stage.usd"
    carb.log_info(f"[InnoactiveStartup] Loading USD file: {emptyStage}")
    omni.usd.get_context().open_stage(emptyStage)
    print("skipping empty stage load")

# Run the script in the event loop
async def main():
    await startup_script()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
