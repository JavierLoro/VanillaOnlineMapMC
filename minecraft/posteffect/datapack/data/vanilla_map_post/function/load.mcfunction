scoreboard objectives add vmp_map trigger
scoreboard objectives add vmp_leaves minecraft.custom:minecraft.leave_game
scoreboard objectives add vmp_session dummy
scoreboard objectives add vmp_slot dummy
scoreboard objectives add vmp_scroll dummy
scoreboard objectives add vmp_zoom dummy
scoreboard objectives add vmp_pan dummy
scoreboard objectives add vmp_yaw dummy
scoreboard objectives add vmp_heading dummy
scoreboard objectives add vmp_pitch dummy
scoreboard objectives add vmp_dx dummy
scoreboard objectives add vmp_dz dummy
scoreboard objectives add vmp_x dummy
scoreboard objectives add vmp_z dummy
scoreboard objectives add vmp_sent_x dummy
scoreboard objectives add vmp_sent_z dummy
scoreboard objectives add vmp_word dummy
scoreboard objectives add vmp_digit dummy
scoreboard players set #pan_step vmp_pan 100
scoreboard players set #radix vmp_pan 16
scoreboard players set #full_turn vmp_pan 36000
scoreboard players set #heading_steps vmp_pan 64
execute as @a[tag=vmp_open] run function vanilla_map_post:close
function vanilla_map_post:pan_config
