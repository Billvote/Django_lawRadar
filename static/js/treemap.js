// --- 공통 상수 및 유틸 함수 ---
const iconMap = {
  '찬성': { icon: '⭕️', text: '이런 법안을 지지해요!', color: 'text-blue-600' },
  '반대': { icon: '❌', text: '이런 법안은 지지하지 않아요', color: 'text-red-600' },
  '기권': { icon: '🚫', text: '이런 법안에는 기권이 많아요', color: 'text-gray-600' },
  '불참': { icon: '😭', text: '이런 법안에는 불참이 많아요', color: 'text-gray-400' }
};

const exceptions = new Set([
  '종로구','중구','용산구','성동구','광진구','동대문구','중랑구','성북구','강북구','도봉구','노원구',
  '은평구','서대문구','마포구','양천구','강서구','구로구','금천구','영등포구','동작구','관악구',
  '서초구','강남구','송파구','강동구','부산진구','동래구','남구','북구','해운대구','사하구',
  '금정구','강서구','연제구','수영구','사상구','기장군','달서구','달성군','군위군','미추홀구',
  '연수구','남동구','부평구','계양구','서구','강화군','옹진군','광산구','유성구','대덕구',
  '울주군','세종시','수원시','용인시','고양시','화성시','성남시','부천시','남양주시','안산시',
  '평택시','안양시','시흥시','파주시','김포시','의정부시','광주시','하남시','광명시','군포시',
  '양주시','오산시','이천시','안성시','구리시','포천시','양평군','여주시','동두천시','양구군',
  '가평군','연천군','춘천시','원주시','강릉시','동해시','태백시','속초시','삼척시','구례군',
  '홍천군','횡성군','영월군','평창군','정선군','철원군','화천군','양구군','인제군','고성군',
  '양양군','청주시','충주시','제천시','보은군','옥천군','영동군','증평군','진천군','괴산군',
  '음성군','단양군','천안시','공주시','보령시','아산시','서산시','논산시','계룡시','당진시',
  '금산군','부여군','서천군','청양군','홍성군','예산군','태안군','전주시','군산시','익산시',
  '정읍시','남원시','김제시','완주군','진안군','무주군','장수군','임실군','순창군','고창군',
  '부안군','목포시','여수시','순천시','나주시','광양시','담양군','곡성군','구례군','고흥군',
  '보성군','화순군','장흥군','강진군','해남군','영암군','무안군','함평군','영광군','장성군',
  '완도군','진도군','신안군','포항시','경주시','김천시','안동시','구미시','영주시','영천시',
  '상주시','문경시','경산시','의성군','청송군','영양군','영덕군','청도군','고령군','성주군',
  '칠곡군','예천군','봉화군','울진군','울릉군','창원시','진주시','통영시','사천시','김해시',
  '밀양시','거제시','양산시','의령군','함안군','창녕군','고성군','남해군','하동군','산청군',
  '함양군','거창군','합천군','제주시','서귀포시','중구','동구','남구','세종시','동구','군위'
]);

function debounce(func, wait) {
  let timeout;
  return function (...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

function formatNameWithLineBreak(name) {
  if (exceptions.has(name)) return name;
  return name.replace(/(.*[^\s])(시|군|구)$/g, (_, prefix, suffix) => `${prefix}${suffix}<br>`);
}

function getClusterText(type, keywords) {
  const info = iconMap[type];
  if (!info) return '';
  return `
    <div class="mb-4 flex items-start ${info.color} font-bold text-2xl mt-2">
      <div class="whitespace-nowrap">
        <span class="mr-2">${info.icon}</span>
        <span>${info.text}</span>
      </div>
    </div>
  `;
}
// --- DOM 요소 및 전역 변수 ---
const container = document.getElementById("treemap");
const backButton = d3.select("#backButton");
const breadcrumb = document.getElementById("breadcrumb");
const popupModal = document.getElementById("popupModal");
const popupOverlay = document.getElementById("popupOverlay");
const closeModalBtn = document.getElementById("closeModalBtn");
const modalTitle = document.getElementById("modalTitle");
const modalContent = document.getElementById("modalContent");
const backModalBtn = document.getElementById("backModalBtn");
const mainContent = document.getElementById("mainContent");

let svg, currentNode, hierarchyRoot;
let selectedAge = null;
let defaultAgeBtn = null;

// --- 색상 팔레트 정의 ---
const freshColors = [
  "#bef264", "#67e8f9", "#f9a8d4", "#fde68a", "#fdba74",
  "#6ee7b7", "#7dd3fc", "#c4b5fd", "#fda4af", "#5eead4"
];
const sidoColors = d3.scaleOrdinal(freshColors);
const sigunguColors = d3.scaleOrdinal(freshColors);

// --- 팝업 함수 ---
function openPopup(title, contentHtml) {
  modalTitle.textContent = title;
  modalContent.innerHTML = contentHtml;
  popupModal.classList.remove("hidden");
  mainContent.classList.add("opacity-70", "blur-sm");
}
function closePopup() {
  popupModal.classList.add("hidden");
  mainContent.classList.remove("opacity-70", "blur-sm");
}

// 팝업 닫기 이벤트 연결
closeModalBtn.addEventListener("click", closePopup);
popupOverlay.addEventListener("click", closePopup);

// --- Breadcrumb 갱신 ---
function updateBreadcrumb(node) {
  let path = [];
  let current = node;
  while (current) {
    if (current.depth > 0) path.unshift(current.data.name.split(" ")[0]);
    current = current.parent;
  }
  breadcrumb.textContent = path.length ? path.join(" > ") : "";

  if (backButton) {
    backButton.classed("hidden", !node.parent);
  }
}

// --- 표결 요약 HTML 생성 ---
function renderSummary(data) {
  if (!data || Object.keys(data).length === 0) {
    return "<p>데이터가 없습니다.</p>";
  }

  const voteTypes = ['찬성', '반대', '기권', '불참'];
  const uniqueClusters = new Set();
  let html = '<div class="space-y-4">';

  if (data.alignment_rate !== undefined && data.party) {
    html += `
      <div class="p-2 bg-white border border-gray-300 border-l-4 border-l-cyan-400 text-gray-700 rounded shadow-sm text-center">
        <div class="text-lg font-semibold">
          ${data.party}과의 표결 일치율 💡
        </div>
        <div class="text-2xl font-bold mt-2 text-cyan-400">
          ${data.alignment_rate.toFixed(1)}%
        </div>
        <div class="text-sm text-gray-600 mt-1">
          이탈 지수: ${data.deviation_rate.toFixed(1)}%
        </div>
      </div>
    `;
  }

  voteTypes.forEach(type => {
    const item = data[type];
    if (!item) return;
    if (uniqueClusters.has(item.cluster_keyword)) return;
    uniqueClusters.add(item.cluster_keyword);

    let keywords = [];
    if (item.cluster_keyword.startsWith('[')) {
      try {
        keywords = JSON.parse(item.cluster_keyword.replace(/'/g, '"'));
      } catch {
        keywords = [];
      }
    } else {
      keywords = item.cluster_keyword.split(',').map(k => k.trim());
    }

    html += `
      <div class="card rounded-lg shadow-md bg-white p-4">
        ${getClusterText(type, keywords)}
        <div class="flex flex-wrap gap-2 mb-4">
          ${keywords.map(k => `
            <a href="/cardnews/cluster/${item.cluster_id}/">
              <span class="inline-block bg-gray-100 text-gray-600 px-3 py-1 rounded-full text-lg font-semibold cursor-pointer hover:bg-gray-200 transition">
                ${k}
              </span>
            </a>
          `).join('')}
        </div>
        <div class="text-base text-gray-600 mb-4">
          📢 이 키워드의 법안이 궁금하다면? ☝️ Click!
        </div>
        <hr class="my-2 border-gray-200">
        <div class="flex gap-4">
          <div class="flex-1 text-center">
            <div class="text-gray-500 text-sm">찬성</div>
            <div class="text-2xl font-bold text-indigo-600">${item.ratios.찬성.toFixed(1)}%</div>
          </div>
          <div class="flex-1 text-center">
            <div class="text-gray-500 text-sm">반대</div>
            <div class="text-2xl font-bold text-red-600">${item.ratios.반대.toFixed(1)}%</div>
          </div>
          <div class="flex-1 text-center">
            <div class="text-gray-500 text-sm">기권</div>
            <div class="text-2xl font-bold text-gray-600">${item.ratios.기권.toFixed(1)}%</div>
          </div>
          <div class="flex-1 text-center">
            <div class="text-gray-500 text-sm">불참</div>
            <div class="text-2xl font-bold text-gray-400">${item.ratios.불참.toFixed(1)}%</div>
          </div>
        </div>
        <div class="mt-2 text-sm text-gray-500">법안 수: ${item.bill_count}</div>
      </div>
    `;
  });

  html += '</div>';
  return html;
}

  // 뒤로가기 버튼
  backButton.on("click", () => {
    if (currentNode.parent) {
      currentNode = currentNode.parent;
    }
    render(currentNode, container.clientWidth, container.clientHeight);  // 2) 트리맵 다시 그리기 (상위 노드 기준)
    updateBreadcrumb(currentNode); // 3) breadcrumb 갱신
  });

  // 대수 버튼 클릭 이벤트
  document.querySelectorAll(".age-btn").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const newAge = btn.dataset.age;
      selectedAge = newAge;
      
      document.querySelectorAll(".age-btn").forEach(b => b.classList.remove("text-cyan-500", "bg-indigo-600"));
      btn.classList.add("text-cyan-500");
      await init(newAge);
    });
  });

  document.querySelectorAll(".explain-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const title = btn.dataset.title;
      const content = btn.dataset.content;
      openPopup(title, content);
    });
  });

// --- 트리맵 렌더링 함수 ---
function render(node, width, height, selectedMemberName = null) {
  if (!node) return;

  d3.select("#treemap svg").remove();
  const treemapContainer = d3.select("#treemap");
  treemapContainer.selectAll(".district-cards").remove();

  updateBreadcrumb(node);

  const isDistrictLevel =
    node.children && node.children.every(d => d.data.type === "District");

// District 레벨일 때 카드 UI 렌더링
  if (isDistrictLevel) {
    const container = treemapContainer
      .append("div")
      .attr("class", "district-cards grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 p-4");

    node.children.forEach(d => {
      const isSelected = selectedMemberName && d.data.member_name === selectedMemberName;

      const card = container.append("div")
        .attr("class", `district-card${isSelected ? " selected" : ""} bg-white rounded-xl p-4 shadow-lg hover:shadow-xl transition-all duration-500 ease-in-out transform hover:-translate-y-1 cursor-pointer`)
        .style("border-color", d.data.color || "#888")
        .on("click", async () => {
          const memberName = d.data.member_name;
          if (!memberName) {
            alert("이 지역구에는 등록된 의원 정보가 없습니다.");
            return;
          }
          try {
            const res = await fetch(`/geovote/api/member-vote-summary/?member_name=${encodeURIComponent(memberName)}`);
            if (!res.ok) throw new Error("API 호출 실패");
            const summary = await res.json();

            // 정당 일치율 API 추가 호출
            const alignmentRes = await fetch(`/geovote/api/member-alignment/?member_name=${encodeURIComponent(memberName)}&congress_num=${selectedAge}`);
            if (alignmentRes.ok) {
              const alignment = await alignmentRes.json();
              summary.party = alignment.party;
              summary.alignment_rate = alignment.alignment_rate;
              summary.deviation_rate = alignment.deviation_rate;
            }

            const summaryHtml = renderSummary(summary);
            openPopup(`${memberName} 의원은 이렇게 투표했네요 📝🗳️`, summaryHtml);
          } catch (err) {
            console.error(err);
            alert("표결 정보를 가져오지 못했습니다.");
          }
        });

      card.append("img")
        .attr("src", d.data.image_url || "https://via.placeholder.com/100")
        .attr("alt", d.data.member_name || "의원 사진 없음");

      const content = card.append("div").attr("class", "district-card-content");
      const rawDistrictName = d.data.name || "선거구명 없음";
      const districtName = rawDistrictName.split('(')[0].trim();
      const memberName = d.data.member_name || "";

      let party = "";
      const partyMatch = rawDistrictName.match(/\(([^)]+)\)/);
      if (partyMatch) {
        const inside = partyMatch[1];
        const parts = inside.split(" - ");
        if (parts.length === 2) party = parts[1];
      }

      content.append("div")
        .attr("class", "district-card-info")
        .text(memberName || "의원 정보 없음");

      content.append("div")
        .attr("class", "district-card-name")
        .text(districtName);

      content.append("div")
        .attr("class", "district-card-party")
        .style("color", d.data.color || "#888")
        .text(party || "정당 정보 없음");
    });

    return; // 카드 UI 렌더링 후 종료
  }

  // 트리맵 렌더링
  container.innerHTML = ''; // 기존 내용 클리어
  svg = d3.select(container).append("svg")
    .attr("width", width)
    .attr("height", height);
  const group = svg.append("g");
  const x = d3.scaleLinear().domain([node.x0, node.x1]).range([0, width]);
  const y = d3.scaleLinear().domain([node.y0, node.y1]).range([0, height]);

  const childrenToShow = (node.depth <= 1)
    ? (node.children || []).filter(d => d.data.type !== "District")
    : (node.children || []);

  const nodes = group.selectAll("g")
    .data(childrenToShow)
    .join("g")
    .attr("transform", d => `translate(${x(d.x0)},${y(d.y0)})`)
    .style("cursor", d => d.children ? "pointer" : "default")
    .on("click", async (event, d) => {
      if (d.children) {
        currentNode = d;
        render(d, width, height);
      } else if (d.data.type === "District") {
        const memberName = d.data.member_name;
        if (!memberName) {
          alert("이 지역구에는 등록된 의원 정보가 없습니다.");
          return;
        }
        try {
          const res = await fetch(`/geovote/api/member-vote-summary/?member_name=${encodeURIComponent(memberName)}`);
          if (!res.ok) throw new Error("API 호출 실패");
          const summary = await res.json();
          const summaryHtml = renderSummary(summary);
          openPopup(`${memberName} 의원 표결 요약`, summaryHtml);
        } catch (err) {
          console.error(err);
          alert("표결 정보를 가져오지 못했습니다.");
        }
      }
    });


  nodes.append("rect")
    .transition().duration(300)
    .attr("width", d => x(d.x1) - x(d.x0))
    .attr("height", d => y(d.y1) - y(d.y0))
    .attr("rx", 5)
    .attr("ry", 5)
    .attr("fill", d => {
      if (d.data.type === "District") return d.data.color || "#888";
      if (d.data.type === "SIDO") return sidoColors(d.data.name);
      if (d.data.type === "SIGUNGU") return sigunguColors(d.data.name);
      return "#ccc";
    });

      nodes.append("foreignObject")
      .attr("x", 0)
      .attr("y", 0)
      .attr("width", d => (x(d.x1) - x(d.x0)) - 2)   // 2px 여유 줌
      .attr("height", d => (y(d.y1) - y(d.y0)) - 2)
      .append("xhtml:div")
      .attr("class", "node-label")
      .style("width", d => `${x(d.x1) - x(d.x0)}px`)
      .style("height", d => `${y(d.y1) - y(d.y0)}px`)
      .style("display", "flex")
      .style("align-items", "center")
      .style("justify-content", "center")
      .style("text-align", "center")
      .style("font-family", "'Cafe24Ssurround', 'Pretendard', 'Noto Sans KR', 'Nanum Gothic', sans-serif")
      .style("font-weight", "600")
      .style("letter-spacing", "0.02em")
      .style("color", d => {
        if (d.data.type === "SIDO") return "#4A6FA5";
        if (d.data.type === "SIGUNGU") return "#6A8CA3";
        return "#222";
      })
      .style("font-size", d => {
        const width = x(d.x1) - x(d.x0);
        const height = y(d.y1) - y(d.y0);
        const diag = Math.sqrt(width * width + height * height);

        // 예: 대각선 길이를 10으로 나눠서 기본 크기 설정
        let fontSize = diag / 10;

        // 최소/최대 제한 걸기
        fontSize = Math.min(fontSize, 28);
        fontSize = Math.max(fontSize, 10);

        return fontSize + "px";
      })
      .style("line-height", "1.2")
      .style("padding", "0px")
      .style("box-sizing", "border-box")
      .style("word-wrap", "break-word")
      .html(d => {
        return formatNameWithLineBreak(d.data.name);
      });
    }

async function loadData(age) {
  const res = await fetch(`/geovote/api/region-tree/?age=${age}`);
  if (!res.ok) {
    console.error("데이터 로드 실패");
    return null;
  }
  return await res.json();
}

async function init(selectedAge) {
  try {
    const res = await fetch(`/geovote/api/treemap-data/?age=${selectedAge}`);
    if (!res.ok) throw new Error("트리맵 데이터를 가져오지 못했습니다.");
    const data = await res.json();
    const root = d3.hierarchy(data).sum(d => d.value || 1).sort((a, b) => b.value - a.value);
    const width = container.clientWidth * 0.95;
    const height = container.clientHeight * 0.9;

    d3.treemap().size([width, height]).padding(2)(root);
    hierarchyRoot = root;
    currentNode = root;
    render(root, width, height);
  } catch (err) {
    console.error(err);
    alert("트리맵 초기 데이터를 가져오지 못했습니다.");
  }
}

function resize() {
  if (!hierarchyRoot || !currentNode) return;
  const padding = 20;
  const width = container.clientWidth - padding;
  const height = container.clientHeight - padding;
  render(currentNode, width, height);
}

document.addEventListener("DOMContentLoaded", () => {
  const ageButtons = document.querySelectorAll(".age-btn");

  ageButtons.forEach(btn => {
    btn.addEventListener("click", async () => {
      const newAge = btn.dataset.age;
      selectedAge = newAge;
      ageButtons.forEach(b => b.classList.remove("text-cyan-500", "bg-indigo-600"));
      btn.classList.add("text-cyan-500");
      await init(newAge);
    });
  });

  defaultAgeBtn = [...ageButtons].find(btn => btn.textContent.trim() === "22대") || ageButtons[0];
  if (defaultAgeBtn) {
    defaultAgeBtn.classList.add("text-cyan-500");
    selectedAge = defaultAgeBtn.dataset.age;
    init(selectedAge);
  }

  window.addEventListener("resize", debounce(resize, 200));
});
   
