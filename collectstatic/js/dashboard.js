// 기본 통계 차트------------------
  const series = {{ series|safe }};
  const colors = {{ party_colors|safe }};
  const categories = {{ categories|safe }};
  const partyNames = {{ party_names|safe }};
  // const partyColors = {{ party_colors|safe }};
  // const resultTypes = ['찬성', '반대', '기권', '불참'];
  // const clusterKeywords = {{ cluster_keywords|safe }};
  // const clusterNums = JSON.parse('{{ cluster_nums|safe }}');

  var options = {
    chart: {
      type: 'bar',
      stacked: true,
      stackType: '100%',
      height: 400,
    },
    plotOptions: {
      bar: {
        horizontal: true,  // 가로 막대
        columnWidth: '60%',
      }
    },
    dataLabels: {
      enabled: true,
      formatter: function (val) {
        return val > 0 ? val.toFixed(1) + '%' : '';
      },
    },
    stroke: {
      show: true,
      width: 1,
      colors: ['transparent']
    },
    series: series,
    xaxis: {
      categories: categories,  // x축: 표결 결과
      title: {
        text: '비율 (%)'
      },
      labels: {
        formatter: function(val) {
          return val.toFixed(0) + '%';
        }
      }
    },
    yaxis: {
      title: {
        text: '정당'
      },
      categories: categories,
    },
    colors: colors,
    legend: {
      position: 'top'
    },
    fill: {
      opacity: 1
    },
    tooltip: {
        y: {
          formatter: function (value) {
            return value + '%';
          }
        }
      }
    };
  new ApexCharts(document.querySelector("#voteChart"), options).render();

  // 클러스터별 표결 결과 차트-------------------------------
document.addEventListener('DOMContentLoaded', () => {
  const clusterSelect = document.getElementById('clusterSelect');
    const clusterVoteData = JSON.parse(document.getElementById("cluster-vote-data").textContent);
    const resultTypes = JSON.parse(document.getElementById("cluster-categories").textContent);
    const partyNames = JSON.parse(document.getElementById("cluster-party-names").textContent);
    const partyColors = JSON.parse(document.getElementById("cluster-party-colors").textContent);

    if (!clusterSelect) {
      console.error("clusterSelect element not found!");
      return;
    }

    const clusterKeys = Object.keys(clusterVoteData);
    clusterKeys.forEach(key => {
      const cluster = clusterVoteData[key];
      const option = document.createElement('option');
      option.value = cluster.cluster_num;  // 실제 클러스터 번호 (29, 30 등)
      option.textContent = `Cluster ${cluster.cluster_num}: ${cluster.cluster_keywords}`;
      // clusterSelect.appendChild(option);
    });

    let clusterChart = null;

  function drawClusterChart(clusterNum) {
    const clusterObj = Object.values(clusterVoteData).find(c => c.cluster_num == clusterNum);
    // const data = clusterObj?.votes;
    // console.log('drawClusterChart called with:', clusterNum);

    if (!clusterObj) {
        console.warn("No data for cluster:", clusterNum);
        const chartContainer = document.querySelector("#clusterVoteChart");
        chartContainer.innerHTML = '<p class="text-center text-gray-500">선택한 클러스터에 대한 데이터가 없습니다.</p>';
        if (clusterChart) {
          clusterChart.destroy();
          clusterChart = null;
        }
        return;
      }

      const partyStats = clusterObj.party_stats;

    // resultTypes, partName 매칭
    const series = partyNames.map(party => {
      const stats = partyStats[party];
      return {
        name: party,
        data: resultTypes.map(type => stats ? stats[type] : 0)
    };
  });

    // 차트 옵션
    const options = {
      chart: {
        type: 'bar',
        stacked: true,
        stackType: '100%',
        height: 400,
      },
      plotOptions: {
        bar: {
          horizontal: true,
          columnWidth: '60%',
        }
      },
      dataLabels: {
        enabled: true,
        formatter: function(val, opts) {
          // 각 막대의 비율을 표시하는데, 해당 값이 0보다 클 경우에만 표시
          const partyIndex = opts.seriesIndex;  // 각 시리즈의 인덱스(찬성, 반대 등)
          const partyName = partyNames[partyIndex];  // 해당 시리즈에 해당하는 정당 이름
          return val.toFixed(1) + '%';}
      },
      stroke: {
        show: true,
        width: 1,
        colors: ['transparent'] // 막대 경계선
      },
      series: series,
      xaxis: {
        categories: resultTypes,
        title: { text: '비율 (%)' }, // X축 제목
        labels: {
          formatter: function (val) {
            return val.toFixed(0) + '%'; // 100% 단위로 표시
            }
          }
        },
      yaxis: {
        categories: partyNames,
        title: { text: '정당' },
        // categories: categories
      },
      colors: partyColors,
      legend: { position: 'top' }, // 범례 위치
      fill: { opacity: 1 },
      tooltip: {
        y: {
          formatter: function (value) {
            return value + '%';
          }
        }
      }
    };


    if (clusterChart) {
      clusterChart.updateOptions(options, true, true);
    } else {
        const chartContainer = document.querySelector("#clusterVoteChart");
        if (chartContainer) {
          clusterChart = new ApexCharts(chartContainer, options);
          clusterChart.render();
        } else {
          console.error("Chart container #clusterVoteChart not found!");
        }
      }
    }

  // 초기 렌더링
  if (clusterSelect && clusterSelect.value) {
      drawClusterChart(clusterSelect.value);
    } else {
      console.error("Cluster select element not found or no value!");
    }

    // 선택 시 다시 그리기
    clusterSelect.addEventListener('change', e => {
      drawClusterChart(e.target.value);
    });
  });

// 권력 집중도 시계열-----------
  document.addEventListener('DOMContentLoaded', function () {
    const ages = {{ timeseries_data_age|safe }};
    const hhiValues = {{ timeseries_data_hhi|safe }};
    const enpValues = {{ timeseries_data_enp|safe }};
    const top2Ratios = {{ timeseries_data_top2_ratio|safe }};

    const options = {
      chart: { type: 'line', height: 350 },
      xaxis: { categories: ages, title: { text: '국회 대수' } },
      yaxis: [
      {
        seriesName: 'HHI 지수',
        title: { text: 'HHI 지수' },
        min: 0,
        max: 1,
        opposite: false,
      },
      {
        seriesName: '점유율 (%)',
        title: { text: '점유율 (%)' },
        min: 0,
        max: 100,
        opposite: true,
      }
    ],
    series: [
      {
        name: 'HHI 지수',
        type: 'line',
        data: hhiValues,
        yAxisIndex: 0,
      },
      {
        name: '점유율 (%)',
        type: 'line',
        data: top2Ratios,
        yAxisIndex: 1,
      }
    ],
    tooltip: {
      shared: true,
      intersect: false
    }
  };

    const chart = new ApexCharts(document.querySelector("#hhi-top2-chart"), options);
    chart.render();
  });

// enp 프로그래스 바------------------
document.addEventListener("DOMContentLoaded", function () {
  const ages = {{ timeseries_data_age|safe }};
  const enpValues = {{ timeseries_data_enp|safe }};
  const totalParties = {{ timeseries_data_total_parties|safe }};
  
  const container = document.getElementById("enp-progress-bars");

  for (let i = 0; i < ages.length; i++) {
    const ratio = ((enpValues[i] / totalParties[i]) * 100).toFixed(1);

    const barWrapper = document.createElement("div");
    barWrapper.style.marginBottom = "12px";

barWrapper.innerHTML = `
  <div class="mb-5">
    <div class="flex justify-between items-center mb-1">
      <div class="flex items-center gap-2">
        <svg class="w-4 h-4 text-pink-500" fill="currentColor" viewBox="0 0 20 20">
          <path d="M2 10a8 8 0 1116 0A8 8 0 012 10z" />
        </svg>
        <span class="font-semibold text-gray-800">${ages[i]}</span>
      </div>
      <span class="text-sm text-gray-500">총 ${totalParties[i]}개 정당 중 ${enpValues[i]}개 (${ratio}%)</span>
    </div>
    <div class="w-full bg-gray-100 rounded-full h-4">
      <div class="bg-gradient-to-r from-pink-400 to-pink-600 h-4 rounded-full text-xs text-white text-right pr-2 font-medium"
           style="width: ${ratio}%; min-width: 2rem;">
        ${ratio}%
      </div>
    </div>
  </div>
`;


    container.appendChild(barWrapper);
  }
});

// 팝업------------
  const popupModal = document.getElementById("popupModal");
  const popupOverlay = document.getElementById("popupOverlay");
  const closeModalBtn = document.getElementById("closeModalBtn");
  const modalTitle = document.getElementById("modalTitle");
  const modalContent = document.getElementById("modalContent");
  const mainContent = document.querySelector(".flex-1.p-6");

  // 팝업 열기
  function openPopup(title, contentHtml) {
    modalTitle.textContent = title;
    modalContent.innerHTML = contentHtml;
    popupModal.classList.remove("hidden");
    mainContent.classList.add("opacity-70", "blur-sm"); // 메인 콘텐츠 흐림
  }

  // 팝업 닫기
  function closePopup() {
    popupModal.classList.add("hidden");
    mainContent.classList.remove("opacity-70", "blur-sm");
  }

    // 버튼 이벤트 등록
  closeModalBtn.addEventListener("click", closePopup);
  popupOverlay.addEventListener("click", closePopup);

document.querySelectorAll(".explain-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const title = btn.dataset.title;
    const content = btn.dataset.content;
    openPopup(title, content);
  });
});


// 정당별 탑 클러스터 차트-------------------------------------
document.addEventListener("DOMContentLoaded", function () {
  const ageNum = {{ congress_num|safe }};
  const stanceSelect = document.getElementById("stanceSelect");
  const topSelect = document.getElementById("topSelect");
  const chartContainer = document.getElementById("topClusterChart");
  let chart;
  // console.log("topSelect.value:", topSelect.value);

  if (!stanceSelect || !topSelect || !chartContainer) {
    console.error("필수 DOM 요소가 없습니다.");
    return;
  }
  // ✅ 1. 이 자리에 추가해줘 (fetchAndRenderChart 앞이면 좋아)
  function filterTopSelectOptionsByStance() {
    const selectedStance = stanceSelect.value;

    Array.from(topSelect.options).forEach(option => {
      const stance = option.getAttribute("data-stance");
      if (stance === selectedStance) {
        option.style.display = "";
      } else {
        option.style.display = "none";
      }
    });

    // 필터된 첫 옵션으로 기본 선택 설정
    const firstVisibleOption = Array.from(topSelect.options).find(
      option => option.style.display !== "none"
    );
    if (firstVisibleOption) {
      topSelect.value = firstVisibleOption.value;
      // 강제로 change 이벤트 트리거 (그래야 fetchAndRenderChart가 호출됨)
      const event = new Event('change');
      topSelect.dispatchEvent(event);
    }
  }


function getSelectedParams() {
    // stanceSelect 값은 "oppose" or "abstain" 형태, topSelect는 "party--stance--clusterNum" 형태라 가정
    const stance = stanceSelect.value;
    const selectedTop = topSelect.value;
    const [party, topStance, clusterNum] = selectedTop.split("--");
    console.log(selectedTop)
    console.log(topSelect)

    // 만약 topStance랑 stanceSelect가 같은 의미라면 조합이 필요할 수도 있음
    // 여기서는 단순히 topSelect에 클러스터 번호만 중요하다고 가정
    return { ageNum, clusterNum, stance, party };
  }

  function fetchAndRenderChart() {
    const { ageNum, clusterNum, party, stance } = getSelectedParams();

    if (!clusterNum) {
      console.warn("clusterNum이 없습니다.");
      return;
    }

    const url = `/api/cluster_chart?age_num=${ageNum}&cluster_num=${clusterNum}&party=${party}&stance=${stance}`;

    fetch(url)
      .then(res => {
        if (!res.ok) throw new Error("서버 응답 오류");
        return res.json();
      })
      .then(data => {
        if (chart) {
          chart.updateOptions({
            xaxis: { categories: data.categories },
            series: data.series
          });
        } else {
          chart = new ApexCharts(chartContainer, {
            chart: {
              type: 'bar',
              stacked: true,
              height: 400
            },
            plotOptions: {
              bar: {
                horizontal: false,
                borderRadius: 4
              }
            },
            xaxis: {
              categories: data.categories
            },
            yaxis: {
              title: { text: "비율 (%)" },
              max: 100
            },
            tooltip: {
              y: { formatter: val => `${val}%` }
            },
            series: data.series
          });
          chart.render();
        }
      })
      .catch(err => {
        console.error("차트 데이터 불러오기 실패:", err);
      });
  }

  // 두 select가 바뀔 때마다 차트 다시 그림
  stanceSelect.addEventListener("change", function () {
  filterTopSelectOptionsByStance();  // 클러스터 옵션 필터링
  // fetchAndRenderChart();             // 차트 다시 그림
});
  topSelect.addEventListener("change", fetchAndRenderChart);

  // 페이지 로드 시 자동 렌더링 (두 select 첫 값으로)
  // fetchAndRenderChart();

  // ✅ 3. 페이지 첫 로딩 시: 옵션 필터링 먼저, 차트 렌더링 그 다음!
  filterTopSelectOptionsByStance();   // ⭐⭐ 이거 반드시 먼저!
  fetchAndRenderChart();              // 그 다음 차트 호출
});

// 카드 뉴스로 이동하기----------------------------------------
document.addEventListener("DOMContentLoaded", function () {
  const selectEl = document.getElementById("topSelect");
  const btn = document.getElementById("goToCardnewsBtn");

  btn.addEventListener("click", function () {
    const selected = selectEl.options[selectEl.selectedIndex];
    const url = selected.dataset.url;
    if (url) {
      window.open(url, "_blank"); // 새 탭으로 열기 (원하면 _self로 수정)
    }
  });
});


// 스크롤 내리면 부드럽게 무빙---------------------------------
document.addEventListener('DOMContentLoaded', function() {
  const observerOptions = {
    threshold: 0.3,
    rootMargin: '0px 0px -100px 0px'
  };

  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, observerOptions);

  // 카드들 애니메이션
  document.querySelectorAll('.timeline-item').forEach((item, index) => {
    item.style.opacity = '0';
    item.style.transform = 'translateY(40px)';
    item.style.transition = `opacity 0.6s ease ${index * 0.1}s, transform 0.6s ease ${index * 0.1}s`;
    observer.observe(item);
  });
});