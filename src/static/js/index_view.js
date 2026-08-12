/**
 * index_view.js  (Entry Point)
 * 대시보드 메인 뷰 모듈 진입점
 *
 * 로드 순서:
 *   1. latest_homework_card.js  - 최근 숙제 & 피드백 카드 렌더러
 *   2. crawler_modal.js         - 크롤러 모달 + 차트 접기/펼치기 토글
 *   3. quick_basket.js          - 퀵 숙제 장바구니 Drawer
 *   4. drilldown_filter.js      - 3열 계층형 드릴다운 패널 + 드래그 선택
 *
 * 각 모듈은 index.html 하단에서 defer 속성으로 개별 로드됩니다.
 * 이 파일은 공통 설정(APP_CONFIG 단축 참조)만 담당합니다.
 */

const CFG_MAIN = window.APP_CONFIG || {};
const userUuid = CFG_MAIN.userUuid || CFG_MAIN.viewUsername || "";
