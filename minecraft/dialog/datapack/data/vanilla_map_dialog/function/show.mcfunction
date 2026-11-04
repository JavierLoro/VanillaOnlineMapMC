# Each dialog is assembled and sent synchronously for one player.
data modify storage vanilla_map_dialog:work view set from storage vanilla_map_dialog:atlas dialog
execute store result score #x vmd_calc store result storage vanilla_map_dialog:work args.x int 1 run data get entity @s Pos[0] 1
execute store result score #z vmd_calc store result storage vanilla_map_dialog:work args.z int 1 run data get entity @s Pos[2] 1
execute if dimension minecraft:overworld run function vanilla_map_dialog:marker
execute unless dimension minecraft:overworld run data modify storage vanilla_map_dialog:work view.title[1].text set value " | Position available in the Overworld"
execute if score @s vmd_sector matches 1.. if score @s vmd_sector <= #sectors vmd_calc run function vanilla_map_dialog:sector
function vanilla_map_dialog:send with storage vanilla_map_dialog:work
