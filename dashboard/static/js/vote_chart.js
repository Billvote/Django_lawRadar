export function renderVoteChart(data) {
  const { series, categories, partyColors } = data;
  const resultTypes = ['찬성', '반대', '기권', '불참'];

  const options = {
    chart: { type: 'bar', stacked: true, stackType: '100%', height: 400 },
    plotOptions: { bar: { horizontal: true, columnWidth: '60%' } },
    dataLabels: {
      enabled: true,
      formatter: val => (val > 0 ? val.toFixed(1) + '%' : ''),
    },
    stroke: { show: true, width: 1, colors: ['transparent'] },
    series: series,
    xaxis: {
      categories: resultTypes,
      title: { text: '비율 (%)' },
      labels: { formatter: val => val.toFixed(0) + '%' },
    },
    yaxis: { title: { text: '정당' }, categories: categories },
    colors: partyColors,
    legend: { position: 'top' },
    fill: { opacity: 1 },
  };

  const chartElement = document.querySelector("#voteChart");
  if (chartElement) {
    chartElement.innerHTML = ''; // 이전 차트 제거
    new ApexCharts(chartElement, options).render();
  } else {
    console.error("#voteChart element not found.");
  }
}