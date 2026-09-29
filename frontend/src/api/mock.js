export const mockVideos = [
  { video_id:1, video_name:'50个摔倒的动作.mp4', path:'E:/VideoSage/data/videos/50个摔倒的动作.mp4', duration:232.98, fps:23.98, width:640, height:360, status:'completed', create_time:'2026-09-19 17:19' },
  { video_id:2, video_name:'行走参考.mp4', path:'E:/VideoSage/data/videos/行走参考.mp4', duration:186.42, fps:30, width:1280, height:720, status:'completed', create_time:'2026-09-19 13:48' }
]
export const mockPersons = [
  { video_id:1, person_id:1, first_seen:2.34, last_seen:232.94, occurrence_count:5096, primary_action:'standing', outfit:'黑色短袖 / 灰色长裤' },
  { video_id:2, person_id:1, first_seen:0.12, last_seen:186.2, occurrence_count:3920, primary_action:'walking', outfit:'蓝色短袖 / 黑色长裤' }
]
export const mockAnomalies = [
  { video_id:1, person_id:1, event:'fall', start_time:4.38, end_time:5.55, confidence:0.98, severity:'high' },
  { video_id:1, person_id:1, event:'lying', start_time:8.59, end_time:10.55, confidence:0.95, severity:'normal' }
]
const behaviors=[{action:'standing',start_time:2.34,end_time:4.17,confidence:.82},{action:'walking',start_time:4.17,end_time:8.59,confidence:.76},{action:'sitting',start_time:8.59,end_time:11.2,confidence:.81}]
export const mockPerson=(videoId,personId)=>({ video_id:videoId, person_id:personId, first_seen:2.34,last_seen:232.94, pose:{record_count:5096,keypoint_count:17,status:'关键点覆盖良好'}, behaviors, outfit:{upper_color:'black',upper_type:'short_sleeve_top',upper_sleeve:'short_sleeve',lower_color:'gray',lower_type:'pants',lower_length:'long',confidence:.78,sample_count:194}, anomalies:mockAnomalies.filter(x=>x.video_id===videoId&&x.person_id===personId) })
export const mockVideo=id=>({ ...mockVideos.find(x=>x.video_id===id), stats:{persons:1,behaviors:36,anomalies:12,outfits:1} })
export const mockDashboard={ stats:{videos:2,tasks:2,persons:2,anomalies:12}, behaviors:{standing:38,walking:27,sitting:19,unknown:8}, anomalies:{fall:6,lying:4,running:2}, trend:[{date:'09-15',count:1},{date:'09-16',count:2},{date:'09-17',count:2},{date:'09-18',count:4},{date:'09-19',count:6}] }
