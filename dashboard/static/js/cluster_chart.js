export function renderClusterChart(data) {
  const ApexCharts = window.ApexCharts;
  const {
    clusterVoteData,
    partyNames,
    partyColors,
    clusterNums,
  } = data;

  const resultTypes = ['찬성', '반대', '기권', '불참'];
  const clusterSelect = document.getElementById('clusterSelect');
  const chartContainer = document.querySelector("#clusterVoteChart");

  let clusterChart = null;

  function draw(clusterNum) {
    const data = clusterVoteData.cluster_data[clusterNum];
    if (!data) {
      chartContainer.innerHTML = '<p class="text-center text-gray-500">선택한 클러스터에 대한 데이터가 없습니다.</p>';
      if (clusterChart) clusterChart.destroy();
      return;
    }

    const series = partyNames.map(party => ({
      name: party,
      data: resultTypes.map(type => data[party]?.[type] || 0),
    }));

    const options = {
      chart: { type: 'bar', stacked: true, stackType: '100%', height: 400 },
      plotOptions: { bar: { horizontal: true, columnWidth: '60%' } },
      dataLabels: {
        enabled: true,
        formatter: val => val.toFixed(1) + '%',
      },
      stroke: { show: true, width: 1, colors: ['transparent'] },
      series: series,
      xaxis: {
        categories: resultTypes,
        title: { text: '비율 (%)' },
        labels: { formatter: val => val.toFixed(0) + '%' },
      },
      yaxis: {
        categories: partyNames,
        title: { text: '정당' },
      },
      colors: partyColors,
      legend: { position: 'top' },
      fill: { opacity: 1 },
    };

    if (clusterChart) {
      clusterChart.updateOptions(options, true, true);
    } else {
      clusterChart = new ApexCharts(chartContainer, options);
      clusterChart.render();
    }
  }

  if (clusterSelect && clusterSelect.value) draw(clusterSelect.value);

  clusterSelect.addEventListener('change', e => {
    draw(e.target.value);
  });
}
