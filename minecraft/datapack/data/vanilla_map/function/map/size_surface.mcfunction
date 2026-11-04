# Match the rendered model to Floating UI's raycast area.
data modify entity @s transformation.scale[0] set from entity @s item.components."minecraft:custom_data".data.size[0]
data modify entity @s transformation.scale[1] set from entity @s item.components."minecraft:custom_data".data.size[1]
