scoreboard objectives add vm_open trigger
scoreboard objectives add vm_state dummy
scoreboard objectives add vm_zoom dummy
scoreboard objectives add vm_col dummy
scoreboard objectives add vm_row dummy
scoreboard objectives add vm_pin_x dummy
scoreboard objectives add vm_pin_z dummy
scoreboard objectives add vm_index dummy
scoreboard objectives add vm_pan dummy
scoreboard objectives add vm_cool dummy
scoreboard players set #zero vm_state 0
scoreboard players set #two vm_state 2
scoreboard players set #width vm_state 256
scoreboard players set #height vm_state 144
scoreboard players set #panel_w vm_state 48000
scoreboard players set #panel_h vm_state 27000
scoreboard players set #half_w vm_state 24000
scoreboard players set #half_h vm_state 13500
scoreboard players set #button_w vm_state 6000
execute unless data storage vanilla_map:points owners run data modify storage vanilla_map:points owners set value []
function vanilla_map:load_atlas
execute unless data storage vanilla_map:system initialized if function floating_ui:util/check/world_entity run data modify storage vanilla_map:system initialized set value 1b
execute unless data storage vanilla_map:system initialized run function floating_ui:load
execute if function floating_ui:util/check/world_entity run data modify storage vanilla_map:system initialized set value 1b
