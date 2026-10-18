#extension GL_OES_EGL_image_external_essl3 : require
precision highp float;
uniform samplerExternalOES sTexture;
uniform vec2 resolution;
uniform bool enablePeak;
uniform bool mirror;
// Rounded viewfinder corners (px, 0 = square). Fragments outside the rounded
// rect are dropped so the blurred backdrop beneath the preview shows through.
uniform float uCornerRadius;
// Sharp rect origin in GL surface pixels, so the mask is built in screen space
// (texCoord is rotated by the vertex shader and would stretch the arcs).
uniform vec2 uSharpOrigin;
out vec4 Output;
in vec2 texCoord;
uniform bool m10rEnabled;
uniform highp sampler2D m10rLut;
uniform highp sampler2D m10rInverse;
uniform mat3 m10rUndo;
uniform float m10rExposureScale;
float m10rDecode(float y, int channel) {
    float p=clamp(y,0.0,1.0)*1023.0;
    float lo=floor(p),hi=min(lo+1.0,1023.0);
    vec3 a=(texture(m10rInverse,vec2((lo+.5)/1024.0,.25)).rgb*65280.0
            +texture(m10rInverse,vec2((lo+.5)/1024.0,.75)).rgb*255.0)/65535.0;
    vec3 b=(texture(m10rInverse,vec2((hi+.5)/1024.0,.25)).rgb*65280.0
            +texture(m10rInverse,vec2((hi+.5)/1024.0,.75)).rgb*255.0)/65535.0;
    return mix(a[channel],b[channel],p-lo);
}
vec3 m10rRender(vec3 encoded) {
    vec3 linear=vec3(m10rDecode(encoded.r,0),m10rDecode(encoded.g,1),m10rDecode(encoded.b,2));
    vec3 sensor=clamp((m10rUndo*linear)*m10rExposureScale,0.0,4.0);
    vec3 p=log(vec3(1.0)+15.0*sensor)/log(61.0)*32.0;
    float b=floor(p.b),nextB=min(b+1.0,32.0);
    vec3 low=texture(m10rLut,vec2((b*33.0+p.r+.5)/1089.0,(p.g+.5)/33.0)).rgb;
    vec3 high=texture(m10rLut,vec2((nextB*33.0+p.r+.5)/1089.0,(p.g+.5)/33.0)).rgb;
    return mix(low,high,p.b-b);
}
void main() {
    if (uCornerRadius > 0.0) {
        vec2 halfSize = resolution * 0.5;
        vec2 local = gl_FragCoord.xy - uSharpOrigin;
        vec2 q = abs(local - halfSize) - (halfSize - vec2(uCornerRadius));
        float cornerDist = length(max(q, vec2(0.0)))
                + min(max(q.x, q.y), 0.0) - uCornerRadius;
        if (cornerDist > 0.0)
            discard;
    }
    vec2 uv = texCoord.xy;
    if(mirror)
        uv.y = 1.0 - uv.y;
    vec4 color = texture(sTexture, uv);
    vec3 m10rColour=m10rEnabled?m10rRender(color.rgb):color.rgb;
    vec2 size = resolution;
    // focus peaking
    vec4 avg = vec4(0.0);
    for (int i = -1; i <= 1; i++) {
        for (int j = -1; j <= 1; j++) {
            avg += texture(sTexture, uv + vec2(i*2, j*2) / size);
        }
    }
    avg /= 9.0;
    float diff = dot(abs(color - avg), vec4(0.299, 0.587, 0.114, 0.0));
    float denoiseK = 0.05;
    // denoise
    float w = (diff * diff) /(denoiseK + (diff * diff));
    vec4 dc = vec4(1.0,0.0,1.0,0.0);
    color.rgb=m10rColour;
    if(enablePeak)
        color = color + dc*32.0*diff*w;
    Output = color;
}
