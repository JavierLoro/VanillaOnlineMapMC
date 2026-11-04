$execute unless data storage vanilla_map:points owners[{uuid:$(uuid)}].points[$(index)] run return 0
$data remove storage vanilla_map:points owners[{uuid:$(uuid)}].points[$(index)]
scoreboard players set @s vm_index -1
scoreboard players reset @s vm_pin_x
scoreboard players reset @s vm_pin_z
title @s actionbar {"text":"Map point removed.","color":"green"}
