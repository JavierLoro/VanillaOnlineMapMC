scoreboard players operation #sector vmd_calc = @s vmd_sector
scoreboard players remove #sector vmd_calc 1
execute store result storage vanilla_map_dialog:work args.sector int 1 run scoreboard players get #sector vmd_calc
function vanilla_map_dialog:sector_label with storage vanilla_map_dialog:work args
