import { renderVoteChart } from './vote_chart.js';
import { renderClusterChart } from './cluster_chart.js';

document.addEventListener("DOMContentLoaded", () => {
  const configElement = document.getElementById("chart-config");
  const config = JSON.parse(configElement.textContent);

  if (!configElement) {
    console.error("chart-config element not found.");
    return;
  }

  const config = JSON.parse(configElement.textContent);

  renderVoteChart(config.series, config.categories, config.partyColors);

  const defaultCluster = config.clusterNums[0];
  renderClusterChart(defaultCluster, config.clusterVoteData, config.partyNames, config.partyColors);

  const clusterSelect = document.getElementById("clusterSelect");
  if (clusterSelect) {
    clusterSelect.addEventListener("change", (e) => {
      const selectedCluster = parseInt(e.target.value);
      renderClusterChart(selectedCluster, config.clusterVoteData, config.partyNames, config.partyColors);
    });
  } else {
    console.warn("clusterSelect not found");
  }
});
