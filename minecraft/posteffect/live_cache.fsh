#version 330
#extension GL_ARB_separate_shader_objects : require

uniform sampler2D MainSampler;
uniform sampler2D PreviousSampler;
layout(location = 0) in vec2 texCoord;
layout(location = 0) out vec4 fragColor;
layout(std140) uniform SamplerInfo {
    vec2 OutSize;
    vec2 MainSize;
    vec2 PreviousSize;
};

vec4 bytesAt(sampler2D image, ivec2 p) {
    return round(texelFetch(image, p, 0) * 255.0);
}

bool cacheValid(sampler2D image, ivec2 offset) {
    return all(equal(bytesAt(image, offset + ivec2(2, 16)), vec4(83, 84, 49, 255))) &&
           all(equal(bytesAt(image, offset + ivec2(1, 16)).gba, vec3(76, 86, 255)));
}

void main() {
    ivec2 p = ivec2(gl_FragCoord.xy);
    bool largeEnough = MainSize.x >= 30.0 && MainSize.y >= 19.0;
    bool forwarded = largeEnough && cacheValid(MainSampler, ivec2(0, 2));
    bool previous = cacheValid(PreviousSampler, ivec2(0));
    vec4 old = forwarded ? bytesAt(MainSampler, p + ivec2(0, 2)) :
               previous ? bytesAt(PreviousSampler, p) : vec4(0);
    vec4 origin = forwarded ? bytesAt(MainSampler, ivec2(0, 18)) :
                  previous ? bytesAt(PreviousSampler, ivec2(0, 16)) : vec4(0);
    float revision = forwarded ? bytesAt(MainSampler, ivec2(1, 18)).r :
                     previous ? bytesAt(PreviousSampler, ivec2(1, 16)).r : -1.0;
    float packet[20];
    bool valid = largeEnough;
    float a = 0.0, b = 0.0;
    for (int i = 0; i < 20; ++i) {
        vec4 signal = largeEnough ? bytesAt(MainSampler, ivec2(10 + i, 0)) : vec4(0);
        valid = valid && all(equal(signal.gba, vec3(57, 143, 211)));
        packet[i] = signal.r;
        if (i < 18) { a = mod(a + signal.r, 255.0); b = mod(b + a, 255.0); }
    }
    valid = valid && packet[4] < 64.0 && packet[18] == a && packet[19] == b;
    if (!valid) { fragColor = old / 255.0; return; }
    vec4 nextOrigin = vec4(packet[0], packet[1], packet[2], packet[3]);
    bool same = (forwarded || previous) && all(equal(origin, nextOrigin)) && revision == packet[17];
    vec4 result = same ? old : vec4(0);
    int index = p.y * 16 + p.x;
    if (p.y < 16 && index / 4 == int(packet[4])) {
        int start = 5 + (index % 4) * 3;
        result = vec4(packet[start], packet[start + 1], packet[start + 2], 255);
    }
    if (p.y == 16) {
        if (p.x == 0) result = nextOrigin;
        if (p.x == 1) result = vec4(packet[17], 76, 86, 255);
        if (p.x == 2) result = vec4(83, 84, 49, 255);
    }
    fragColor = result / 255.0;
}
