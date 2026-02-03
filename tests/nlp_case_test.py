import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from interface.nlp_interpreter import CommandInterpreter

ci = CommandInterpreter()
cmd = ci.parse_command("load dir=../../../../../../mnt/BSP_NAS2_work/Acoustics_output_data/Echopype_results/Finngrundet2025/csv/ pattern=SLUAquaSailor2020V2-Phase0-*.csv positions=./data/positions.txt")
print(cmd)
