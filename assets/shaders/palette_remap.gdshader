shader_type canvas_item;

// Snap each ZX ink colour to a modern stand-in. Blended texels (the tile
// layers are filtered) land on the nearest source colour first.
uniform float tolerance = 0.55;
uniform float enabled = 1.0;
uniform vec4 s0 : source_color;
uniform vec4 s1 : source_color;
uniform vec4 s2 : source_color;
uniform vec4 s3 : source_color;
uniform vec4 s4 : source_color;
uniform vec4 s5 : source_color;
uniform vec4 s6 : source_color;
uniform vec4 s7 : source_color;
uniform vec4 s8 : source_color;
uniform vec4 s9 : source_color;
uniform vec4 s10 : source_color;
uniform vec4 s11 : source_color;
uniform vec4 d0 : source_color;
uniform vec4 d1 : source_color;
uniform vec4 d2 : source_color;
uniform vec4 d3 : source_color;
uniform vec4 d4 : source_color;
uniform vec4 d5 : source_color;
uniform vec4 d6 : source_color;
uniform vec4 d7 : source_color;
uniform vec4 d8 : source_color;
uniform vec4 d9 : source_color;
uniform vec4 d10 : source_color;
uniform vec4 d11 : source_color;

void fragment() {
	vec4 texel = texture(TEXTURE, UV);
	vec3 mapped = texel.rgb;
	if (enabled >= 0.5) {
		float best = tolerance;
		float dist;
		dist = distance(texel.rgb, s0.rgb);
		if (dist < best) { best = dist; mapped = d0.rgb; }
		dist = distance(texel.rgb, s1.rgb);
		if (dist < best) { best = dist; mapped = d1.rgb; }
		dist = distance(texel.rgb, s2.rgb);
		if (dist < best) { best = dist; mapped = d2.rgb; }
		dist = distance(texel.rgb, s3.rgb);
		if (dist < best) { best = dist; mapped = d3.rgb; }
		dist = distance(texel.rgb, s4.rgb);
		if (dist < best) { best = dist; mapped = d4.rgb; }
		dist = distance(texel.rgb, s5.rgb);
		if (dist < best) { best = dist; mapped = d5.rgb; }
		dist = distance(texel.rgb, s6.rgb);
		if (dist < best) { best = dist; mapped = d6.rgb; }
		dist = distance(texel.rgb, s7.rgb);
		if (dist < best) { best = dist; mapped = d7.rgb; }
		dist = distance(texel.rgb, s8.rgb);
		if (dist < best) { best = dist; mapped = d8.rgb; }
		dist = distance(texel.rgb, s9.rgb);
		if (dist < best) { best = dist; mapped = d9.rgb; }
		dist = distance(texel.rgb, s10.rgb);
		if (dist < best) { best = dist; mapped = d10.rgb; }
		dist = distance(texel.rgb, s11.rgb);
		if (dist < best) { best = dist; mapped = d11.rgb; }
	}
	COLOR = vec4(mapped, texel.a);
}

void light() {
	LIGHT = vec4(COLOR.rgb * LIGHT_COLOR.rgb * LIGHT_ENERGY, LIGHT_COLOR.a);
}
