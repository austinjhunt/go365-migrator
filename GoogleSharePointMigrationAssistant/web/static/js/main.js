let CSRF_TOKEN;
let toasty;
document.addEventListener("DOMContentLoaded", function () {
  CSRF_TOKEN = document.querySelector('input[name=csrfmiddlewaretoken]').value;
  function removeFadeOut(el, speed) {
    var seconds = speed / 1000;
    el.style.transition = "opacity " + seconds + "s ease";
    el.style.opacity = 0;
    setTimeout(function () {
      el.parentNode.removeChild(el);
    }, speed);
  }
  setTimeout(function () {
    console.log("fading out");
    removeFadeOut(document.querySelector(".loader_container_wrapper"), 300);
  }, 1000);
  // initialize data tables
  $(".datatable").DataTable({ pageLength: 5 });

  // initialize toasts
  toasty = new bootstrap.Toast(document.querySelector('.toast'));
});

let selectSourceForMigration = (btn) => {
  let selectedRow = btn.parentNode.parentNode;
  let selectionsContainer = document.querySelector("#google-file-selections");
  let elem = document.createElement("div");
  let text = document.createElement("span");
  text.textContent = `${selectedRow.dataset.name} (${selectedRow.dataset.mimetypefriendly})`;
  elem.appendChild(text);
  elem.dataset.id = selectedRow.dataset.id;
  elem.dataset.mimetypefriendly = selectedRow.dataset.mimetypefriendly;
  elem.dataset.name = selectedRow.dataset.name;
  elem.classList.add("bg-info");
  elem.classList.add("p-3");
  elem.classList.add("m-2");
  elem.classList.add("d-block");
  elem.classList.add("rounded");
  elem.classList.add("d-flex");
  elem.classList.add("justify-content-between");
  let deleteButton = document.createElement("button");
  deleteButton.title = "Unselect this item";
  deleteButton.innerHTML = `
  <i class="fa fa-trash"></i> Unselect
  `;
  deleteButton.classList.add("btn");
  deleteButton.classList.add("btn-danger");
  deleteButton.classList.add("btn-sm");
  deleteButton.addEventListener("click", (event) => {
    event.target.parentNode.remove();
  });

  elem.appendChild(deleteButton);
  selectionsContainer.appendChild(elem);
};

let confirmSelectedMigrationSources = () => {
  let selections = [];
  document.querySelectorAll("google-file-selections div").forEach((el) => {
    selections.push({
      id: el.dataset.id,
    });
  });
  fetch("/confirm-migration-sources/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": CSRF_TOKEN,
    },
    body: JSON.stringify({ selections: selections }),
  })
    .then((response) => response.json())
    .then((data) => {
      let toast = document.querySelector('.toast');
      if ('success' in data){
        toast.querySelector('.toast-header strong').textContent = 'Confirmed';
        toast.querySelector('.toast-body').textContent = 'Your selected migration sources are confirmed.';
        toasty.show();
      } else if ('error' in data){ 
        toast.querySelector('.toast-header strong').textContent = 'Error';
        toast.querySelector('.toast-body').textContent = data['error'];
        toasty.show();
      }
      
    });
};
