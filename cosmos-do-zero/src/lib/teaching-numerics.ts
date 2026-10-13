import {comovingMpc,PLANCK,C_KMS} from './cosmology';
/** Hogg, NED HTML sections4/7, comoving and luminosity distances and distance modulus. Same H0; reference is EdS without radiation.
 * The teaching points are generated, not observations. z=0 uses the common local limit. */
export function deltaMagnitude(z:number):number{if(!Number.isFinite(z)||z<0)throw RangeError('redshift');if(z===0)return 0;const eds=2*C_KMS/PLANCK.h0*(1-1/Math.sqrt(1+z));return 5*Math.log10(comovingMpc(z,PLANCK)/eds);}
/** Ordinary least squares, independent homoscedastic errors. SE is not a confidence level. */
export function linearFit(points:readonly (readonly [number,number])[]){const n=points.length;if(n<3||points.some(p=>p.some(x=>!Number.isFinite(x))))return null;const mx=points.reduce((s,p)=>s+p[0],0)/n,my=points.reduce((s,p)=>s+p[1],0)/n,sxx=points.reduce((s,p)=>s+(p[0]-mx)**2,0);if(sxx===0)return null;const b=points.reduce((s,p)=>s+(p[0]-mx)*(p[1]-my),0)/sxx,a=my-b*mx,res=points.reduce((s,p)=>s+(p[1]-a-b*p[0])**2,0)/(n-2);return {a,b,slopeSE:Math.sqrt(res/sxx),meanSE:(x:number)=>Math.sqrt(res*(1/n+(x-mx)**2/sxx))};}
/** U.S. Standard Atmosphere1976, Part1 pp3–4,9–11, tables4/8, eqs23,27,29.
 * Input geometric km; conversion to geopotential below86km. Not current weather.
 * Rounded M/M0 table interpolated in80–86km (sub0.01K precision adequate for integer°C display). */
export function atmosphereTemperatureC(z:number):number{if(!Number.isFinite(z)||z<0||z>120)throw RangeError('altitude0–120km');if(z>=110)return 240+12*(z-110)-273.15;if(z>91)return 263.1905-76.3232*Math.sqrt(1-((z-91)/19.9429)**2)-273.15;if(z>=86)return 186.8673-273.15;const h=6356.766*z/(6356.766+z),hs=[0,11,20,32,47,51,71],rates=[-6.5,0,1,2.8,0,-2.8,-2];let t=288.15;for(let i=0;i<hs.length;i++){const end=hs[i+1]??84.852;if(h<=end){t+=rates[i]*(h-hs[i]);break;}t+=rates[i]*(end-hs[i]);}if(z>80){const ratios=[1,.999996,.999988,.999971,.999941,.999909,.999870,.999829,.999786,.999741,.999694,.999641,.9995788],u=(z-80)*2,i=Math.min(11,Math.floor(u));t*=ratios[i]+(ratios[i+1]-ratios[i])*(u-i);}return t-273.15;}
export const atmosphereProfile=Array.from({length:241},(_,i)=>[i/2,atmosphereTemperatureC(i/2)] as [number,number]);
export const atmosphereLayer=(z:number)=>z<12?'troposfera':z<50?'estratosfera':z<85?'mesosfera':'termosfera';
