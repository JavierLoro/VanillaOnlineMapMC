#version 330
#extension GL_ARB_separate_shader_objects : require
uniform sampler2D InSampler;
layout(location = 0) in vec2 texCoord;
layout(location = 0) out vec4 fragColor;
void main() {
    if (any(greaterThanEqual(texCoord, vec2(1)))) discard;
    fragColor = texelFetch(InSampler, ivec2(floor(texCoord * vec2(16, 17))), 0);
}
