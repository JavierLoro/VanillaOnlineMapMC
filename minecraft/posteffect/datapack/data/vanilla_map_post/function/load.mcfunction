scoreboard objectives add vmp_map trigger
scoreboard objectives add vmp_leaves minecraft.custom:minecraft.leave_game
scoreboard objectives add vmp_session dummy
scoreboard objectives add vmp_slot dummy
scoreboard objectives add vmp_scroll dummy
scoreboard objectives add vmp_zoom dummy
execute as @a[tag=vmp_open] run function vanilla_map_post:close
