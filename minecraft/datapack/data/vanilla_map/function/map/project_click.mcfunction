# Project the point on the panel to the center of the corresponding map pixel.
function vanilla_map:map/tile_origin
scoreboard players operation #u vm_state = return_u floating_ui.temp
scoreboard players operation #u vm_state += #half_w vm_state
scoreboard players operation #u vm_state *= #width vm_state
scoreboard players operation #u vm_state /= #panel_w vm_state
scoreboard players operation #v vm_state = #half_h vm_state
scoreboard players operation #v vm_state -= return_v floating_ui.temp
scoreboard players operation #v vm_state *= #height vm_state
scoreboard players operation #v vm_state /= #panel_h vm_state
execute if score #u vm_state matches 256.. run scoreboard players set #u vm_state 255
execute if score #v vm_state matches 144.. run scoreboard players set #v vm_state 143
scoreboard players operation #u vm_state *= #pixel vm_state
scoreboard players operation #v vm_state *= #pixel vm_state
scoreboard players operation #half_pixel vm_state = #pixel vm_state
scoreboard players operation #half_pixel vm_state /= #two vm_state
scoreboard players operation #u vm_state += #half_pixel vm_state
scoreboard players operation #v vm_state += #half_pixel vm_state
scoreboard players operation #u vm_state += #view_x vm_state
scoreboard players operation #v vm_state += #view_z vm_state
