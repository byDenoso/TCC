// All lengths are expressed in equatorial radii. The camera is orthographic.
export const vertex = `
attribute vec2 corner;
varying vec2 uv;
void main() { uv = corner; gl_Position = vec4(corner, 0., 1.); }
`;

export const fragment = `
precision highp float;
varying vec2 uv;
uniform sampler2D surfaceMap;
uniform float elevation;
uniform float longitude;
uniform vec2 size;
const float pi = 3.14159265359;
const float flattening = .904;
const vec3 sun = vec3(-.688, .492, .534);

float band(float inner, float outer, float radius, float soft) {
  return smoothstep(inner-soft,inner+soft,radius)*(1.-smoothstep(outer-soft,outer+soft,radius));
}
float intervalNoise(float x) {
  float i = floor(x), t = fract(x);
  return mix(fract(sin(i*.73+32.)*4375.8),fract(sin((i+1.)*.73+32.)*4375.8),t*t*(3.-2.*t));
}
// Radial optical depth. The boundary of each named band is in planet radii.
float depth(float r, float footprint) {
  float c = .16 * band(1.235,1.524,r,.007);
  float b = (1.15 + .48 * smoothstep(1.60,1.92,r)) * band(1.525,1.948,r,.004);
  float a = .67 * band(2.024,2.269,r,.004);
  a *= 1.-.86 * band(2.207,2.218,r,.002);
  float f = .17 * band(2.319,2.327,r,.002);
  float grain = .72+.45*intervalNoise(r*128.)+.20*intervalNoise(r*630.)*(1.-smoothstep(.0007,.008,footprint));
  grain += .12*sin(r*172.+.37*sin(r*542.)) + .07*sin(r*629.+1.72);
  return max(0.,(c+b+a+f)*grain + .047*band(1.95,2.03,r,.009));
}
vec2 ellipsoid(vec3 o, vec3 d, float k) {
  vec3 axis=vec3(1.,1./flattening,1.)/k;
  vec3 a=o*axis,b=d*axis;
  float aa=dot(b,b), ab=dot(a,b), delta=ab*ab-aa*(dot(a,a)-1.);
  if (delta<0.) return vec2(90.,-90.);
  float root=sqrt(delta);
  return vec2((-ab-root)/aa,(-ab+root)/aa);
}
float planetShadow(vec3 point) {
  // Closest approach of the solar ray to the oblate planet.
  vec3 o=point*vec3(1.,1./flattening,1.);
  vec3 d=sun*vec3(1.,1./flattening,1.);
  float t=max(0.,-dot(o,d)/dot(d,d));
  return smoothstep(.985,1.018,length(o+t*d));
}
void main() {
  float angle=radians(elevation), ca=cos(angle), sa=sin(angle);
  vec3 camera=vec3(0.,sa,ca), up=vec3(0.,ca,-sa), ray=-camera;
  vec2 q=uv*vec2(2.49,2.49*size.y/size.x);
  float roll=radians(18.5), cr=cos(roll), sr=sin(roll);
  q=vec2(cr*q.x+sr*q.y,-sr*q.x+cr*q.y);
  vec3 eye=camera*5.+vec3(q.x,0.,0.)+q.y*up;
  vec2 body=ellipsoid(eye,ray,1.);
  vec4 result=vec4(0.);
  float pixel=4.98/size.x;
  // A short optical-depth integration for the atmospheric rim.
  vec2 shell=ellipsoid(eye,ray,1.020);
  if (shell.x<8. && body.x>8.) {
    float path=shell.y-shell.x, optical=0.;
    vec3 p0=eye+ray*shell.x;
    float side=clamp(.15+dot(normalize(p0),sun),0.,1.);
    for(int i=0;i<8;i++) {
      vec3 p=eye+ray*(shell.x+path*(float(i)+.5)/8.);
      float height=max(0.,length(p*vec3(1.,1./flattening,1.))-1.);
      optical+=exp(-height*217.)*path/8.;
    }
    result=vec4(mix(vec3(.17,.25,.37),vec3(.97,.74,.47),side),clamp(optical*(.25+1.3*side),0.,.38));
  }
  if(body.x<8.) {
    vec3 p=eye+ray*body.x;
    vec3 n=normalize(p*vec3(1.,1./(flattening*flattening),1.));
    float lat=asin(clamp(p.y/flattening,-1.,1.));
    float lon=atan(p.z,p.x)+longitude;
    vec3 map=texture2D(surfaceMap,vec2(fract(lon/(2.*pi)),.5-lat/pi)).rgb;
    float lum=dot(map,vec3(.27,.61,.12));
    float belts=.5+.5*sin(13.*lat + .25*sin(29.*lat));
    vec3 cream=mix(vec3(.61,.45,.34),vec3(1.03,.87,.68),smoothstep(.41,.83,lum));
    cream*=.87+.17*lum+.025*belts+.016*sin(95.*lat+.6*sin(lon*3.)+.7*sin(lat*22.));
    cream+= (map-vec3(lum))*.34;
    float nl=dot(n,sun), nv=max(0.,dot(n,camera));
    float light=pow(clamp(nl+.028,0.,1.),.57);
    float rayDist=-p.y/sun.y;
    if(rayDist>0.) {
      float rr=length((p+sun*rayDist).xz);
      float od=depth(rr,max(pixel,.001));
      light*=mix(.32,1.,exp(-od/sun.y));
    }
    vec3 night=vec3(.040,.063,.108)*(.65+.5*max(0.,n.y)+.2*(1.-nv));
    vec3 color=night+cream*light*.94;
    color+=vec3(.09,.09,.084)*pow(1.-nv,3.)*clamp(nl+.2,0.,1.);
    result=vec4(color,1.);
  }
  float hit=-eye.y/ray.y;
  if(hit>0. && hit<body.x){
    vec3 p=eye+hit*ray; float r=length(p.xz);
    if(r>1.19 && r<2.345){
      float od=depth(r,pixel/max(sa,.2));
      float opacity=1.-exp(-od/max(sa,.12));
      float textureTone=.67+.20*intervalNoise(r*71.)+.16*intervalNoise(r*267.);
      float ash=.62+.12*sin(32.*r)+.14*sin(13.*r);
      vec3 ring=mix(vec3(.49,.54,.60),vec3(.84,.78,.66),clamp(ash-.40*smoothstep(1.87,2.1,r),0.,1.));
      ring*=textureTone*(.75+.2*smoothstep(1.5,1.7,r));
      float shadow=planetShadow(p);
      ring=mix(ring*vec3(.16,.21,.31),ring,shadow);
      float alpha=opacity+result.a*(1.-opacity);
      result=vec4((ring*opacity+result.rgb*result.a*(1.-opacity))/max(alpha,.0001),alpha);
    }
  }
  gl_FragColor=vec4(clamp(result.rgb,0.,1.),result.a);
}
`;
