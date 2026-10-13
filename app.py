from pathlib import Path
import json
import math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title='SmartPrice AI | Retail Pricing', page_icon='🛍️', layout='wide')
BASE = Path(__file__).resolve().parent
OUT = BASE / 'outputs'
REC_FILES = [OUT / 'audited_pricing_recommendations.csv', OUT / 'aligned_pricing_recommendations.csv']
AUDIT_FILE = OUT / 'aligned_pricing_audit.json'

st.markdown('''<style>
.block-container{padding-top:1.4rem;max-width:1500px}
div[data-testid="stMetric"]{background:rgba(128,128,128,.07);border:1px solid rgba(128,128,128,.18);padding:14px;border-radius:12px}
.hero{padding:22px;border-radius:15px;background:linear-gradient(115deg,rgba(48,100,160,.18),rgba(30,160,130,.11));border:1px solid rgba(128,128,128,.2);margin-bottom:18px}
</style>''', unsafe_allow_html=True)

@st.cache_data
def load_data():
    path = next((p for p in REC_FILES if p.exists()), None)
    if path is None:
        return None, None
    d = pd.read_csv(path)
    required = ['item_id','store_id','current_price','recommended_price','predicted_demand','action']
    missing = [c for c in required if c not in d.columns]
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(missing))
    for c in ['current_price','recommended_price','predicted_demand','estimated_profit','hold_estimated_profit','price_change_pct']:
        if c in d.columns: d[c] = pd.to_numeric(d[c], errors='coerce')
    d['item_id'] = d['item_id'].fillna('Unknown item').astype(str)
    d['store_id'] = d['store_id'].fillna('Unknown store').astype(str)
    d['action'] = d['action'].fillna('hold').astype(str).str.lower().str.strip()
    d = d.dropna(subset=['current_price','recommended_price','predicted_demand'])
    d = d[(d.current_price > 0) & (d.recommended_price > 0) & (d.predicted_demand >= 0)].copy()
    d['price_change_pct_calculated'] = (d.recommended_price / d.current_price - 1) * 100
    return d, path.name

@st.cache_data
def load_audit():
    try:
        return json.loads(AUDIT_FILE.read_text(encoding='utf-8')) if AUDIT_FILE.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}

def money(x):
    return '—' if x is None or pd.isna(x) or not np.isfinite(x) else f'${x:,.2f}'
def num(x, n=2):
    return '—' if x is None or pd.isna(x) or not np.isfinite(x) else f'{x:,.{n}f}'
def pct(x, n=1):
    return '—' if x is None or pd.isna(x) or not np.isfinite(x) else f'{x:,.{n}f}%'
def store_name(s):
    names={'CA_1':'California — Store 1','CA_2':'California — Store 2','CA_3':'California — Store 3','CA_4':'California — Store 4','TX_1':'Texas — Store 1','TX_2':'Texas — Store 2','TX_3':'Texas — Store 3','WI_1':'Wisconsin — Store 1','WI_2':'Wisconsin — Store 2','WI_3':'Wisconsin — Store 3'}
    return names.get(str(s), str(s))
ACTIONS={'test_increase':'Test a price increase','apply_markdown':'Consider a markdown','hold':'Keep the current price'}
def action_label(a): return ACTIONS.get(str(a).lower(), str(a).replace('_',' ').title())
def action_emoji(a): return {'test_increase':'🔵','apply_markdown':'🟠','hold':'🟢'}.get(str(a).lower(),'⚪')
def explain(row):
    a=str(row.action).lower(); ch=(float(row.recommended_price)/float(row.current_price)-1)*100
    if a=='test_increase': return f'The pricing rule suggests testing a higher price ({ch:+.1f}%). Test cautiously; this does not prove demand will stay the same.'
    if a=='apply_markdown': return f'The pricing rule suggests considering a lower price ({ch:+.1f}%). Measure the result before applying broadly.'
    return 'The pricing rule suggests keeping the price near its current level because the modeled benefit of changing it may be limited.'

try:
    df, source = load_data(); audit = load_audit(); error = None
except Exception as e:
    df, source, audit, error = None, None, {}, str(e)

st.markdown('''<div class="hero"><h1>🛍️ SmartPrice AI</h1><h3>Retail Demand & Pricing Decision Dashboard</h3><p>Explore product recommendations, compare prices, and test how different demand assumptions affect estimated gross profit.</p></div>''', unsafe_allow_html=True)
if df is None:
    st.error('Pricing recommendations could not be loaded.')
    if error: st.code(error)
    st.markdown('Expected files: `outputs/audited_pricing_recommendations.csv` or `outputs/aligned_pricing_recommendations.csv`. The audit JSON is optional.')
    st.stop()

st.sidebar.title('🧭 SmartPrice AI')
page = st.sidebar.radio('Choose a section',['Business Overview','Explore a Product','Try a Different Price'],key='selected_page')
with st.sidebar.expander('Filter recommendations', expanded=True):
    stores=sorted(df.store_id.unique().tolist())
    chosen_stores=st.multiselect('Stores',stores,default=stores,format_func=store_name)
    action_opts=['test_increase','apply_markdown','hold']
    chosen_actions=st.multiselect('Recommendation type',action_opts,default=action_opts,format_func=action_label)
    search=st.text_input('Search product ID',placeholder='e.g. FOODS_1_001')
    pmin,pmax=float(df.current_price.min()),float(df.current_price.max())
    price_range=(pmin,pmax) if math.isclose(pmin,pmax) else st.slider('Current price range',pmin,pmax,(pmin,pmax),step=.01,format='$%.2f')
st.sidebar.caption(f'Data file: `{source}`')
st.sidebar.caption(f'Valid records: {len(df):,}')
filtered=df[df.store_id.isin(chosen_stores)&df.action.isin(chosen_actions)&df.current_price.between(price_range[0],price_range[1])].copy()
if search.strip(): filtered=filtered[filtered.item_id.str.contains(search.strip(),case=False,na=False,regex=False)]

if page=='Business Overview':
    st.subheader('Business Overview'); st.write('A snapshot of the pricing suggestions in your saved dataset.')
    if filtered.empty: st.warning('No records match these filters. Adjust the sidebar filters.'); st.stop()
    a,b,c,d=st.columns(4)
    a.metric('Product/store records',f'{len(filtered):,}'); b.metric('Unique products',f'{filtered.item_id.nunique():,}'); c.metric('Stores represented',f'{filtered.store_id.nunique():,}'); d.metric('Average suggested price change',pct(filtered.price_change_pct_calculated.mean()))
    st.divider(); left,right=st.columns(2)
    with left:
        st.markdown('#### Recommendation breakdown')
        counts=filtered.action.value_counts().reindex(action_opts,fill_value=0)
        st.bar_chart(pd.DataFrame({'Products':counts.values},index=[action_label(x) for x in counts.index]),horizontal=True)
        st.caption('Suggested actions in the file; these have not necessarily been applied in stores.')
    with right:
        st.markdown('#### Price change distribution')
        changes=filtered.price_change_pct_calculated.dropna()
        if not changes.empty:
            hist=pd.cut(changes,[-100,-20,-10,-5,0,5,10,20,100],include_lowest=True).value_counts(sort=False); hist.index=[str(x) for x in hist.index]; st.bar_chart(hist.rename('Records'))
        else: st.info('No price-change values available.')
    st.divider(); st.markdown('#### Product recommendations')
    table=filtered.copy(); table['Store']=table.store_id.map(store_name); table['Suggested action']=table.action.map(action_label); table['Price change (%)']=table.price_change_pct_calculated
    display=table[['item_id','Store','current_price','recommended_price','Price change (%)','predicted_demand','Suggested action']].rename(columns={'item_id':'Product ID','current_price':'Current price ($)','recommended_price':'Suggested price ($)','predicted_demand':'Estimated units'})
    st.dataframe(display,use_container_width=True,hide_index=True,height=390)
    st.download_button('⬇️ Download filtered recommendations (CSV)',filtered.to_csv(index=False).encode('utf-8'),'smartprice_filtered_recommendations.csv','text/csv')
    with st.expander('Model performance and limitations'):
        if audit:
            x,y,z=st.columns(3)
            if audit.get('validation_mae') is not None: x.metric('Validation MAE',num(audit['validation_mae'],3))
            if audit.get('validation_rmse') is not None: y.metric('Validation RMSE',num(audit['validation_rmse'],3))
            if audit.get('validation_lag1_baseline_mae') is not None: z.metric('Simple baseline MAE',num(audit['validation_lag1_baseline_mae'],3))
            if audit.get('later_test'): st.markdown('**Later-period test**'); st.json(audit['later_test'])
        else: st.info('No audit JSON found. Recommendations are still available.')
        st.warning('MAE/RMSE measure demand-estimation error, not pricing-policy accuracy. The profit comparison is simulated and does not prove a causal effect.')

elif page=='Explore a Product':
    st.subheader('Explore a Product'); st.write('Choose a product/store record to inspect its suggested price and action.')
    if filtered.empty: st.warning('No records match the current filters.'); st.stop()
    products=filtered.copy(); products['selection_label']=products.item_id+'  |  '+products.store_id.map(store_name); labels=products.selection_label.tolist()
    selected=st.selectbox('Select a product and store',labels,key='explore_selection'); row=products[products.selection_label==selected].iloc[0]
    current=float(row.current_price); recommended=float(row.recommended_price); demand=float(row.predicted_demand); change=(recommended/current-1)*100
    st.divider(); st.markdown(f'### {row.item_id}'); st.caption(f'Store: {store_name(row.store_id)}')
    a,b,c=st.columns(3); a.metric('Current price',money(current)); b.metric('Suggested price',money(recommended),delta=f'{change:+.1f}%'); c.metric('Estimated units',num(demand))
    st.markdown('#### Suggested action'); st.info(f"{action_emoji(row.action)} **{action_label(row.action)}**"); st.write(explain(row))
    left,right=st.columns(2)
    with left: st.markdown('#### Price comparison'); st.bar_chart(pd.DataFrame({'Price ($)':[current,recommended]},index=['Current price','Suggested price']))
    with right:
        st.markdown('#### Recommendation details'); st.write(f'- Current price: **{money(current)}**'); st.write(f'- Suggested price: **{money(recommended)}**'); st.write(f'- Difference: **{money(recommended-current)}**'); st.write(f'- Percentage change: **{change:+.1f}%**'); st.write(f'- Saved model demand estimate: **{num(demand)} units**')
        if pd.notna(row.get('estimated_profit',np.nan)): st.write(f"- Saved simulated profit: **{money(float(row['estimated_profit']))}**")
    st.caption('Demand is a model estimate. The recommendation is not a guarantee of future sales.')
    if st.button('➡️ Open simulator for this product',use_container_width=True):
        st.session_state['sim_item_id']=row.item_id; st.session_state['sim_store_id']=row.store_id; st.session_state['selected_page']='Try a Different Price'; st.rerun()

elif page=='Try a Different Price':
    st.subheader('Try a Different Price'); st.write('Change a possible selling price and compare estimated units and gross profit under a stated demand-response assumption.')
    st.warning('Demonstration only: the demand response is an assumption, not a validated elasticity estimate or a new ML prediction.')
    if filtered.empty: st.warning('No records match the current filters.'); st.stop()
    products=filtered.copy(); products['selection_label']=products.item_id+'  |  '+products.store_id.map(store_name); labels=products.selection_label.tolist(); default=0
    remembered_item=st.session_state.get('sim_item_id'); remembered_store=st.session_state.get('sim_store_id')
    if remembered_item is not None and remembered_store is not None:
        matches=products.index[(products.item_id==remembered_item)&(products.store_id==remembered_store)].tolist()
        if matches: default=labels.index(products.loc[matches[0],'selection_label'])
    selected=st.selectbox('Choose a product and store',labels,index=default,key='simulator_product'); row=products[products.selection_label==selected].iloc[0]
    current=float(row.current_price); reference=float(row.recommended_price); base_demand=max(float(row.predicted_demand),0.0)
    st.markdown(f'### {row.item_id} · {store_name(row.store_id)}')
    a,b,c=st.columns(3); a.metric('Current price',money(current)); b.metric('Saved suggested price',money(reference)); c.metric('Saved estimated units',num(base_demand))
    st.divider(); left,right=st.columns([1,1])
    with left:
        st.markdown('#### 1. Set up your scenario'); low=max(.01,min(current,reference)*.5); high=max(current,reference)*2
        if high<=low: high=low+.01
        trial=st.slider('Test selling price ($)',min_value=float(low),max_value=float(high),value=float(min(max(reference,low),high)),step=.01,format='$%.2f',key='trial_price')
        known=st.checkbox('I have a verified unit cost',value=False,help='Leave unchecked if you do not know the actual product cost.')
        if known:
            cost=st.number_input('Verified cost per unit ($)',min_value=.01,max_value=100000.0,value=float(round(max(.01,current*.62),2)),step=.05,key='verified_cost')
            st.caption('Use a cost figure from a reliable business source.')
        else:
            cost=st.number_input('Illustrative cost per unit ($)',min_value=.01,max_value=100000.0,value=float(round(max(.01,current*.62),2)),step=.05,key='assumed_cost')
            st.caption('This is an assumption, not a real product cost. Replace it when you have reliable cost data.')
        response=st.selectbox('Assumed customer response to price',['Mild response','Moderate response','Strong response'],index=1)
        elasticity={'Mild response':-.5,'Moderate response':-1.2,'Strong response':-2.0}[response]
        st.caption(f'Scenario assumption: elasticity = {elasticity:.1f}. More negative means the scenario assumes demand reacts more strongly.')
    price_change=(trial/reference-1)*100 if reference else 0.0
    trial_demand=base_demand*(trial/reference)**elasticity if reference>0 and base_demand>0 else base_demand
    trial_demand=max(0.0,float(trial_demand)); base_profit=(reference-cost)*base_demand; trial_profit=(trial-cost)*trial_demand; demand_change=(trial_demand/base_demand-1)*100 if base_demand>0 else np.nan; profit_change=trial_profit-base_profit
    with right:
        st.markdown('#### 2. Scenario summary'); st.metric('Test price',money(trial),delta=f'{price_change:+.1f}%')
        st.metric('Scenario estimated units',num(trial_demand),delta=f'{demand_change:+.1f}%' if np.isfinite(demand_change) else 'N/A',delta_color='normal')
        # Explicit signed numeric delta + normal direction makes negative changes red.
        st.metric('Scenario gross profit',money(trial_profit),delta=f'${profit_change:+,.2f}',delta_color='normal',help='Gross profit = (selling price − unit cost) × estimated units.')
        if not known: st.caption('Profit uses an illustrative cost assumption.')
    st.divider(); st.markdown('#### 3. Compare the scenarios'); l,r=st.columns(2)
    with l: st.markdown('**Estimated units**'); st.bar_chart(pd.DataFrame({'Units':[base_demand,trial_demand]},index=['Saved recommendation','Your scenario']))
    with r: st.markdown('**Estimated gross profit**'); st.bar_chart(pd.DataFrame({'Gross profit ($)':[base_profit,trial_profit]},index=['Saved recommendation','Your scenario']))
    st.dataframe(pd.DataFrame({'Saved recommendation':[reference,base_demand,base_profit],'Your price scenario':[trial,trial_demand,trial_profit]},index=['Selling price ($)','Estimated units','Estimated gross profit ($)']),use_container_width=True)
    margin=trial-cost; margin_pct=margin/trial*100 if trial>0 else np.nan
    if margin<0: st.error(f'Test price is below entered unit cost. Estimated gross margin per unit: {money(margin)}.')
    elif math.isclose(margin,0,abs_tol=.005): st.info('Test price is approximately equal to the entered unit cost.')
    else: st.success(f'Estimated gross margin per unit: {money(margin)} ({pct(margin_pct)} of selling price).')
    st.caption('Gross profit excludes other expenses, stock constraints, competitor reactions, and operating costs. Scenario demand is extrapolated from the selected assumption, not a validated causal forecast.')
    export=pd.DataFrame([{'item_id':row.item_id,'store_id':row.store_id,'current_price':current,'saved_recommended_price':reference,'saved_predicted_demand':base_demand,'trial_price':trial,'unit_cost_value':cost,'unit_cost_is_verified':known,'response_assumption':response,'assumed_elasticity':elasticity,'scenario_estimated_demand':trial_demand,'reference_gross_profit':base_profit,'scenario_gross_profit':trial_profit,'gross_profit_difference':profit_change,'demand_change_percent':demand_change,'price_change_percent':price_change,'note':'Illustrative scenario; demand response is assumed, not causally validated.'}])
    st.download_button('⬇️ Download this scenario (CSV)',export.to_csv(index=False).encode('utf-8'),f"smartprice_scenario_{row.item_id}_{row.store_id}.csv",'text/csv')

st.divider(); st.caption('SmartPrice AI | Academic demonstration prototype | Demand estimation + rule-based pricing suggestions + scenario analysis'); st.caption('Decision-support demonstration only. Validate recommendations with reliable cost data and measured customer responses before commercial use.')
