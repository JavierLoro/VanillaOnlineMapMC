scoreboard players operation #view_x vm_state = @s vm_col
scoreboard players operation #view_x vm_state *= #tile_w vm_state
scoreboard players operation #view_x vm_state += #atlas_x vm_state
scoreboard players operation #view_z vm_state = @s vm_row
scoreboard players operation #view_z vm_state *= #tile_h vm_state
scoreboard players operation #view_z vm_state += #atlas_z vm_state
