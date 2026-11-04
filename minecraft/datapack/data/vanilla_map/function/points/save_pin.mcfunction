execute unless score @s vm_pin_x matches -30000000..30000000 run return run title @s actionbar {"text":"Select a point on the map first.","color":"yellow"}
scoreboard players operation #u vm_state = @s vm_pin_x
scoreboard players operation #v vm_state = @s vm_pin_z
function vanilla_map:points/save
