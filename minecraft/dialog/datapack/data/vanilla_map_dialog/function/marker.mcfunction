scoreboard players operation #px vmd_calc = #x vmd_calc
scoreboard players operation #pz vmd_calc = #z vmd_calc
scoreboard players operation #px vmd_calc -= #origin_x vmd_calc
scoreboard players operation #pz vmd_calc -= #origin_z vmd_calc
execute if score #px vmd_calc matches ..-1 run return run function vanilla_map_dialog:position_outside with storage vanilla_map_dialog:work args
execute if score #pz vmd_calc matches ..-1 run return run function vanilla_map_dialog:position_outside with storage vanilla_map_dialog:work args
scoreboard players operation #px vmd_calc /= #step vmd_calc
scoreboard players operation #pz vmd_calc /= #step vmd_calc
execute if score #px vmd_calc >= #width vmd_calc run return run function vanilla_map_dialog:position_outside with storage vanilla_map_dialog:work args
execute if score #pz vmd_calc >= #height vmd_calc run return run function vanilla_map_dialog:position_outside with storage vanilla_map_dialog:work args

# The alternate glyph has the same size and click action as the original tile.
scoreboard players operation #column vmd_calc = #px vmd_calc
scoreboard players operation #column vmd_calc /= #tile vmd_calc
scoreboard players operation #row vmd_calc = #pz vmd_calc
scoreboard players operation #row vmd_calc /= #line vmd_calc
scoreboard players operation #entry vmd_calc = #row vmd_calc
scoreboard players operation #entry vmd_calc *= #stride vmd_calc
scoreboard players operation #entry vmd_calc += #column vmd_calc
scoreboard players operation #glyph vmd_calc = #row vmd_calc
scoreboard players operation #glyph vmd_calc *= #columns vmd_calc
scoreboard players operation #glyph vmd_calc += #column vmd_calc
scoreboard players operation #glyph vmd_calc *= #variants vmd_calc
scoreboard players operation #px vmd_calc %= #tile vmd_calc
scoreboard players operation #px vmd_calc /= #marker_step vmd_calc
scoreboard players operation #glyph vmd_calc += #px vmd_calc
scoreboard players add #glyph vmd_calc 1
execute store result storage vanilla_map_dialog:work args.entry int 1 run scoreboard players get #entry vmd_calc
execute store result storage vanilla_map_dialog:work args.glyph int 1 run scoreboard players get #glyph vmd_calc
function vanilla_map_dialog:place_marker with storage vanilla_map_dialog:work args
