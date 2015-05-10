
// Grab a GET parameter from the URL
function GetURLParameter(sParam){
	var sPageURL = window.location.search.substring(1);
	var sURLVariables = sPageURL.split('&');
	
	for (var i = 0; i < sURLVariables.length; i++){
		 var sParameterName = sURLVariables[i].split('=');
		 if (sParameterName[0] == sParam){
		 	return sParameterName[1];
		 }
	}
}

// Download all cubes or rss files for a plate (Returns rsync command)
function rsyncFiles(){
	$('.dropdown-menu').on('click','li a', function(){
					
		var id = $(this).attr('id');
		var plate = GetURLParameter('plateID');
		var version = GetURLParameter('version');
		var table = ($('.sastable').length == 0) ? null : $('.sastable').bootstrapTable('getData');

		// JSON request
		$.post($SCRIPT_ROOT + '/marvin/downloadFiles', {'id':id, 'plate':plate, 'version':version, 'table':JSON.stringify(table)},'json')
		.done(function(data){
			$('#rsyncbox').val(data.result);
		})
		.fail(function(data){
			$('#rsyncbox').val('Request for rsync link failed.');
		});
	});
						
}

// Submit username and password to Inspection DB for trac login
function login(fxn) {

  var form = $('#login_form').serialize();
  console.log(fxn);
  $.post($SCRIPT_ROOT + '/marvin/login', form,'json') 
	  .done(function(data){
		  if (data.result['status'] < 0) {
			  // bad submit
			  resetLogin();
		  } else {
			  // good submit
			  if (data.result['message']!=''){
				  var stat = (data.result['status'] == 0) ? 'danger' : 'success'; 
				  htmlstr = "<div class='alert alert-"+stat+"' role='alert'><h4>" + data.result['message'] + "</h4></div>";
				  $('#loginmessage').html(htmlstr);
			  }
			  if (data.result['status']==1){
			  	  fxn.call(); 
			  }
			
		  }
	  })
	  .fail(function(data){
	  });				

}
	
// Reset Login
function resetLogin() {
	$('#loginform').modal('hide');
	$('#login_form').trigger('reset');	
	$('#loginmessage').empty();
}


// Submit loginform on username enter keypress
$(function() {		
	$('#username').keyup(function(event){
		var fxn = window[$('#fxn').val()];
		if(event.keyCode == 13){
			if ($('#username').val() && $('#password').val()) {
				login(fxn);
			}
		}
	});
});

// Submit loginform on password enter keypress
$(function() {
	$('#password').keyup(function(event){
		var fxn = window[$('#fxn').val()];
		if(event.keyCode == 13){
			if ($('#username').val() && $('#password').val()) {
				login(fxn);
			}
		}
	});
});
