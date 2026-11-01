/** Finite, executable shot grammar. These are worlds/actions, never a palette seed. */
export const HORROR_WORLDS={
 stormship_inquiry:{fiction:false,settings:['weather_deck','chart_room','engine_hold','storm_deck','lifeboat_station','capsize_section','seabed','inquiry_archive'],objects:['turret_ship','chart','steam_engine','rigging','lifeboat','hull_section','wreck','evidence_board'],actions:['sail','trace_route','turn_engine','heel_in_storm','swing_davit','lose_stability','settle','compare_evidence'],shots:['tracking_wide','overhead','mechanical_close','low_deck','shoulder','section_side','descending','tabletop']},
 abandoned_station:{fiction:true,settings:['platform','ticket_office','radio_room','service_corridor','stairwell','records_room','exit_door','dawn_platform'],objects:['investigator','ticket_window','radio','service_door','staircase','file_cabinet','exit_handle','platform_clock'],actions:['arrive','look_through_window','press_radio','open_door','climb','pull_file','release_latch','leave'],shots:['establishing','window_close','hand_close','follow','low_stairs','over_shoulder','handle_close','reverse_wide']}
};
export function buildHorrorPlan(world,scenes){
 const spec=HORROR_WORLDS[world];if(!spec)throw Error('Unsupported horror topic world');
 return {version:1,world,scenes:scenes.map((scene,index)=>({id:scene.id,setting:spec.settings[index],focal_object:spec.objects[index],action:spec.actions[index],shot:spec.shots[index],state_change:`${spec.actions[index]}:start-to-consequence`,source_excerpt_id:scene.evidence_excerpt_id??null}))};
}
export function validateHorrorPlan(story){
 const plan=story.visual_plan,spec=HORROR_WORLDS[plan?.world];
 if(plan?.version!==1||!spec||story.profile!=='horror'||plan.scenes?.length!==8||story.scenes?.length!==8)throw Error('v2 horror requires an authored eight-shot topic visual_plan');
 if(plan.world==='stormship_inquiry'&&!/hms[- ]captain/i.test(story.topic_key||'')&&!/hms-captain/i.test(story.source?.url||''))throw Error('The turret-and-three-mast schematic is HMS Captain, not a universal ship model');
 if(Boolean(story.fiction)!==spec.fiction)throw Error('The abandoned station is fiction; the ship inquiry is a documented schematic');
 for(let i=0;i<8;i++){
  const row=plan.scenes[i];const location=spec.settings.indexOf(row.setting);if(row.id!==story.scenes[i].id||location<0||row.focal_object!==spec.objects[location]||row.action!==spec.actions[location]||!spec.shots.includes(row.shot)||!row.state_change)throw Error('Horror shot does not fit the implemented topic world');
 }
 if(new Set(plan.scenes.map(row=>row.setting)).size<5)throw Error('A topic needs at least five distinct scene settings');
 return plan;
}

export function directedHorrorState(story,index,progress){const plan=validateHorrorPlan(story),spec=HORROR_WORLDS[plan.world],row=plan.scenes[index];return {world:plan.world,stage_index:spec.settings.indexOf(row.setting),setting:row.setting,focal_object:row.focal_object,action:row.action,shot:row.shot,state_change:row.state_change,progress};}
