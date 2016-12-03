/*!
* Javascript for creating the timeline
* Requires jQuery!!!
*/

var doorEvents = [];
var timeline = null;

//Class for representing open/closing DoorEvents
function DoorEvent(eventType, timeString) {
    this.type = eventType;//I.e. open/close or error
    this.timestamp = timeString;//The time of the event as an ISO date/time String
}

//Class representing a period of time as defined as being between 2 DoorEvents
function DoorEventPeriod(start_event, end_event) {
    this.startEvent = start_event; 
    this.endEvent = end_event;
}

function compareDoorEventsByTimestampString(eventA,eventB) {
    if (eventA.timestamp < eventB.timestamp)
        return -1;
    if (eventA.timestamp > eventB.timestamp)
        return 1;
    return 0;
}

function convertDoorEventListToDoorEventPeriodsList(arrayOfDoorEvents) {

    doorEventPeriods = [];
    expectedEventType = 'open';
    previousEvent = null;

    for (i = 0; i < arrayOfDoorEvents.length; i++) {
        currentEvent = arrayOfDoorEvents[i];
        if (currentEvent.type != expectedEventType) {
            continue;//i.e. ignore unexpected events, and move on to the next
        }

        if (previousEvent != null) {
            doorEventPeriods[doorEventPeriods.length] = new DoorEventPeriod(previousEvent, currentEvent);
        }
        if (currentEvent.type == 'open') {//Toggle the event type we're expecting next
            expectedEventType = 'close';
        } else {
            expectedEventType = 'open';
        }
        previousEvent = currentEvent;
    }

    return doorEventPeriods;
}

function xmlHistoryDataLoaded(xml) {
    //$('#debug_field').append('Ajax Succeeded! ');

    var timestampOfLastModification = $($(xml).find('eventLog')).attr('lastModified');
    //$('#last_modified_message').append("(Last Checked: "+timestampOfLastModification+")");
    $(xml).find('doorEvent').each(function () {
        //$('#debug_field').append('Element Found!');
        var type_string = $(this).attr('type');
        var timestamp_string = $(this).attr('timestamp');

        //Add the new door event to the list of existing events
        doorEvents[doorEvents.length] = new DoorEvent(type_string, timestamp_string)
    })

    //Sort the elements from oldest to most recent
    doorEvents.sort(compareDoorEventsByTimestampString);
    
    var doorEventPeriods = convertDoorEventListToDoorEventPeriodsList(doorEvents);

    var garageDoorIsClosedNow = false;
    if(doorEventPeriods[doorEventPeriods.length - 1].endEvent.type == 'close'){
        garageDoorIsClosedNow = true;
    }

    if (garageDoorIsClosedNow) {
        $('#page_title').html('Door Closed');
        $('#big_message_box').html('CLOSED');
        $('#big_message_box').attr('class', "label label-success label-center");
    } else {
        $('#page_title').html('Door OPEN');
        $('#big_message_box').html('OPEN');
        $('#big_message_box').attr('class', "label label-danger label-center");
    }
    

    //$('#debug_field').append("Items found: " + doorEvents.length + ", ");

    //for (i = 0; i < doorEvents.length; i++) {
    //    $('#debug_field').append('<br>"' + doorEvents[i].type + ': ' +  doorEvents[i].timestamp + '", ');
    //}

    //Build the visualization dataset items
    var visDataSetItems = [];//Array of items for the vis js dataset

    
    for (i = 0; i < doorEventPeriods.length; i++) {
        var newDataSetItem = { type: 'background' };
        newDataSetItem.id = i;
        newDataSetItem.content = ' '
        newDataSetItem.start = doorEventPeriods[i].startEvent.timestamp;
        newDataSetItem.end = doorEventPeriods[i].endEvent.timestamp;
        if (doorEventPeriods[i].startEvent.type == 'close') {
            newDataSetItem.className = 'doorClosed';
        } else {
            newDataSetItem.className = 'doorOpen';
        }
        visDataSetItems[visDataSetItems.length] = newDataSetItem; //Add the new bar item to the list
    }

    //As a last step, fill in the time between the last event and the time things were last modified
    if (visDataSetItems.length > 0) {
        var lastVisDataItem = visDataSetItems[visDataSetItems.length - 1];
        var newDataSetItem = { type: 'background' };
        newDataSetItem.id = lastVisDataItem.id + 1; //Increment 1 from the last added item
        newDataSetItem.content = ' '
        newDataSetItem.start = lastVisDataItem.end;
        newDataSetItem.end = timestampOfLastModification;
        if (garageDoorIsClosedNow) {
            newDataSetItem.className = 'doorClosed';
        } else {
            newDataSetItem.className = 'doorOpen';
        }
        visDataSetItems[visDataSetItems.length] = newDataSetItem; //Add the new bar item to the list
    }

    var visualization_items = new vis.DataSet(visDataSetItems);

    // Create a DataSet (allows two way data-binding)
    //var items = new vis.DataSet([
    //{id: 1, content: 'item 1', start: '2014-04-20'},
    //{id: 2, content: '<span class="glyphicon glyphicon-arrow-up"></span> ', start: '2014-04-14'},
    //{id: 3, content: 'item 3', start: '2014-04-18'},
    //{id: 4, content: 'item 4', start: '2014-04-16', end: '2014-04-19'},
    //{id: 5, content: 'item 5', start: '2014-04-25'},
    //{id: 6, content: 'item 6', start: '2014-04-27', type: 'point'},
    //{id: 'B', content: '', start: '2015-03-04', end: '2015-03-05', type: 'background', className: 'doorClosed'},
    //{ id: 'B', content: '', start: '2015-03-06T13:30:23.000Z', end: '2015-03-07T15:29:59.000Z', type: 'background', className: 'doorClosed' }
    //]);


    // Create a Timeline, or clear and update it's data if stuff has changed
    if (timeline == null){
        var visualization_container = document.getElementById('visualization'); // DOM element where the Timeline will be attached
        // Configuration for the Timeline
        var visualization_options = {
            showCurrentTime: true,
            start: new Date(Date.now() - 1000 * 60 * 60 * 3), //i.e. show previous 3 hours
            end: new Date(Date.now() + 1000 * 60 * 60 * 0.5) // show next 0.5 hours
        };
        timeline = new vis.Timeline(visualization_container, visualization_items, visualization_options);
    }else {
        timeline.clear();
        timeline.setItems(visualization_items);
    }

 }

function updatePageData() {

    $.ajax({
        type: "GET",
        url: "recentActivity.xml",
        dataType: "xml",
        async: true,
        success: xmlHistoryDataLoaded
        //    success: function (xml) {
        //        $('#debug_field').append('Ajax Succeeded! ');
        //        $(xml).find('doorEvent').each(function () {
        //            $('#debug_field').append('Element Found!');
        //            var type_string = $(this).attr('type');
        //            typeStrings[typeStrings.length] = type_string
        //        })
        //    }
    })

}

//Starting Point!
$(document).ready(function(){

    updatePageData();

    //window.setInterval( updatePageData , 59000);//Have the page automaticlly periodically check for updated data (every 59 seconds)

});