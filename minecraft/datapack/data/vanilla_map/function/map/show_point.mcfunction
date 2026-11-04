# Find the tile containing the supplied world coordinates.
function vanilla_map:map/prepare
scoreboard players operation @s vm_col = #u vm_state
scoreboard players operation @s vm_col -= #atlas_x vm_state
scoreboard players operation @s vm_col /= #tile_w vm_state
scoreboard players operation @s vm_row = #v vm_state
scoreboard players operation @s vm_row -= #atlas_z vm_state
scoreboard players operation @s vm_row /= #tile_h vm_state
function vanilla_map:map/update
