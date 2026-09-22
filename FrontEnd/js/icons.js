/* Ícones do ChurrasPlan_Unificado_Completo, adaptados ao frontend multipágina. */
(function(global){
const paths={
home:'m3 10 9-7 9 7M5 9v12h14V9M9 21v-8h6v8',

gift:'M3 8h18v4H3ZM5 12v9h14v-9M12 8v13M12 8C3 8 5 1 9 3c2 1 3 5 3 5Zm0 0c9 0 7-7 3-5-2 1-3 5-3 5Z',building:'M4 21V4h11v17M15 10h5v11M8 8h3M8 12h3M8 16h3M2 21h20',sparkles:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',search:'m16 16 5 5|circle:10,10,7',heart:'M20 5c-3-3-7-1-8 1-1-2-5-4-8-1-6 6 8 16 8 16S26 11 20 5Z',close:'m6 6 12 12M6 18 18 6',history:'M3 10a9 9 0 1 1 2 8M3 3v7h7M12 7v5l3 2',

flame:'M12 3c2 6-4 6-2 11 1-3 3-4 5-6 6 7 2 13-3 13s-9-5-6-10c0 3 2 4 3 4-2-5 4-7 3-12Z',
users:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75|circle:9,7,4',
sliders:'M4 7h9m4 0h3M4 17h3m4 0h9M13 4v6M7 14v6',
chart:'M4 4v16h16M8 16v-5m5 5V7m5 9v-7',
bag:'M5 7h14l1 14H4L5 7ZM9 8V6a3 3 0 0 1 6 0v2',
lock:'M6 10h12v11H6ZM8 10V6a4 4 0 0 1 8 0v4M12 14v3',
sprout:'M12 21V11M12 15C3 16 3 7 3 7s9-1 9 8Zm0-4c0-9 9-8 9-8s0 9-9 8Z',
sun:'M12 2v2m0 16v2M2 12h2m16 0h2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42|circle:12,12,4',
moon:'M20.9 13a9 9 0 0 1-9.9-9.9A9 9 0 1 0 20.9 13Z',
clock:'M12 6v6l4 2|circle:12,12,9',
leaf:'M20 3c-10 0-17 2-17 9a7 7 0 0 0 7 7c7 0 9-6 10-16ZM4 21l10-10',
utensils:'M4 3v6a3 3 0 0 0 6 0V3M7 3v19M20 22V3c-5 3-5 11 0 11',
check:'m5 12 4 4L19 6',chevron:'m6 9 6 6 6-6',arrow:'M4 12h16m-6-6 6 6-6 6',
rotate:'M3 10a9 9 0 1 1 2 8M3 3v7h7',
info:'M12 11v6m0-10v.1|circle:12,12,9',
glass:'M6 3h12l-1 18H7L6 3ZM7 9h10m-5-6 3-2',
drop:'M12 3c-3 5-8 8-8 12a8 8 0 0 0 16 0c0-4-5-7-8-12Z',
citrus:'M12 3a9 9 0 1 0 9 9h-9V3Zm0 9-6-6m6 6-9 1m9-1-5 7m5-7 2 9',
snow:'M12 2v20M3.34 7l17.32 10M3.34 17 20.66 7M9 4l3 3 3-3M9 20l3-3 3 3M3 10l4-1-1-4M18 19l-1-4 4-1M3 14l4 1-1 4M18 5l-1 4 4 1',
save:'M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h12l4 4v12a2 2 0 0 1-2 2ZM7 3v6h10V3M7 21v-8h10v8',
beef:'M14 3c4-1 8 2 7 6s-4 4-5 7-4 6-8 5S1 17 3 12s7-8 11-9ZM8 12c2-2 5-1 4 2s-5 2-4-2Z',
lightbulb:'M9 18h6m-5 3h4M8.1 14a6 6 0 1 1 7.8 0c-1.2 1-1.9 2-1.9 4h-4c0-2-.7-3-1.9-4Z',
copy:'M8 8h13v13H8ZM16 4V3H3v13h1',
print:'M6 9V3h12v6M6 18H3v-9h18v9h-3M6 14h12v7H6ZM17 12h1',
download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
store:'M3 9h18l-2-6H5L3 9ZM4 9v12h16V9M9 21v-7h6v7M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0'
};
function icon(name){const p=paths[name]||paths.info;const [d,c]=p.split('|circle:');return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/>${c?`<circle cx="${c.split(',')[0]}" cy="${c.split(',')[1]}" r="${c.split(',')[2]}"/>`:''}</svg>`;}
function hydrate(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{if(!el.querySelector('svg.icon'))el.innerHTML=icon(el.dataset.icon);});}
global.ChurrasIcons={icon,hydrate};
document.addEventListener('DOMContentLoaded',()=>hydrate());
})(window);
