/* Interações visuais da home unificada. Não substitui as regras do FastAPI. */
(function(){
  function fmt(v, casas=2){return Number(v).toLocaleString('pt-BR',{minimumFractionDigits:casas,maximumFractionDigits:casas});}
  function calcularDemo(total){
    const criancas=Math.round(total*0.20);
    const adultos=total-criancas;
    // Mesmas bases do backend para 4h, almoço e perfil normal.
    const carne=(adultos*0.40)+(criancas*0.20);
    const bebidas=total*(0.75+0.50); // água + refrigerante no exemplo
    return {adultos,criancas,carne,bebidas,picanha:carne*0.60,linguica:carne*0.40};
  }
  function atualizarTrilha(range){
    const min=Number(range.min)||0;
    const max=Number(range.max)||100;
    const valor=Number(range.value);
    const progresso=max>min?((valor-min)/(max-min))*100:0;
    range.style.setProperty('--range-progress',`${Math.max(0,Math.min(100,progresso))}%`);
  }
  function init(){
    const range=document.getElementById('demo-range');
    if(!range)return;
    const totalEl=document.getElementById('demo-total');
    const assumptions=document.getElementById('demo-assumptions');
    const meat=document.getElementById('demo-meat');
    const drinks=document.getElementById('demo-drinks');
    const breakdown=document.getElementById('demo-breakdown');
    const minus=document.getElementById('demo-minus');
    const plus=document.getElementById('demo-plus');
    function update(){
      const total=Number(range.value); const r=calcularDemo(total);
      atualizarTrilha(range);
      totalEl.textContent=total;
      assumptions.textContent=`${r.adultos} adultos + ${r.criancas} crianças · 4 horas · perfil normal`;
      meat.textContent=fmt(r.carne,2)+' kg';
      drinks.textContent=fmt(r.bebidas,1)+' L';
      breakdown.innerHTML=`<div><span>Picanha (60%)</span><strong>${fmt(r.picanha,2)} kg</strong></div><div><span>Linguiça (40%)</span><strong>${fmt(r.linguica,2)} kg</strong></div>`;
      minus.disabled=total<=Number(range.min);plus.disabled=total>=Number(range.max);
    }
    range.addEventListener('input',update);
    minus.addEventListener('click',()=>{range.value=Math.max(Number(range.min),Number(range.value)-1);update();});
    plus.addEventListener('click',()=>{range.value=Math.min(Number(range.max),Number(range.value)+1);update();});
    update();
  }
  document.addEventListener('DOMContentLoaded',init);
})();
